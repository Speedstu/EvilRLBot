"""Static bot/runtime detector used by EvilRLBot.

No RLBot import on purpose: this module is safe to use from both the v4 and v5
Python environments.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
import re
from typing import Iterable



OBS_PROFILES = {
    "NextoObsBuilder": {
        "family": "entity-qkv",
        "state_adapter": "rlgym_compat",
        "previous_action": True,
        "entities": ["self", "teammates", "opponents", "ball", "boosts"],
        "query_width": 32,
        "key_value_width": 24,
        "typical_tick_skip": 8,
    },
    "NectoObsBuilder": {
        "family": "entity-attention",
        "state_adapter": "rlgym_compat",
        "previous_action": True,
        "entities": ["self", "teammates", "opponents", "ball", "boosts"],
        "typical_tick_skip": 8,
    },
    "AdvancedObs": {
        "family": "flat-vector",
        "state_adapter": "rlgym_compat",
        "previous_action": True,
        "team-size-dependent": True,
        "typical_tick_skip": 8,
    },
    "DefaultObs": {
        "family": "flat-vector",
        "state_adapter": "rlgym-v1-or-v2",
        "previous_action": False,
        "team-size-dependent": True,
    },
    "RelativeDefaultObs": {
        "family": "relative-flat-vector",
        "state_adapter": "rlgym-v2",
        "previous_action": False,
        "team-size-dependent": True,
    },
    "Nexto-like entity QKV": {
        "family": "entity-qkv",
        "state_adapter": "rlgym_compat",
        "previous_action": True,
        "entities": ["self", "teammates", "opponents", "ball", "boosts"],
    },
}

SKIP_DIRS = {
    ".git", ".venv", ".venv-v4", "venv", "__pycache__", "node_modules",
    "build", "dist", ".generated",
}


@dataclass
class Detection:
    framework: str = "unknown"
    framework_confidence: float = 0.0
    observation: str = "unknown"
    observation_confidence: float = 0.0
    observation_details: dict = field(default_factory=dict)
    action_parser: str = "unknown"
    tick_skip: int | None = None
    model_runtime: str = "unknown"
    model_files: list[str] = field(default_factory=list)
    configs: list[str] = field(default_factory=list)
    entrypoints: list[str] = field(default_factory=list)
    features: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self):
        return asdict(self)


def _iter_files(root: Path) -> Iterable[Path]:
    if root.is_file():
        yield root
        root = root.parent
    count = 0
    for p in root.rglob("*"):
        if count >= 800:
            break
        if not p.is_file():
            continue
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        if p.suffix.lower() in {
            ".py", ".cfg", ".toml", ".ini", ".json", ".md",
            ".onnx", ".pt", ".pth", ".jit", ".tflite",
        }:
            count += 1
            yield p


def _text_files(files: list[Path]) -> tuple[str, list[tuple[Path, str]]]:
    parts: list[str] = []
    detailed: list[tuple[Path, str]] = []
    budget = 3_000_000
    for p in files:
        if p.suffix.lower() not in {".py", ".cfg", ".toml", ".ini", ".json", ".md"}:
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if len(text) > 250_000:
            text = text[:250_000]
        detailed.append((p, text))
        if budget > 0:
            take = text[:budget]
            parts.append(f"\n# FILE:{p.name}\n{take}")
            budget -= len(take)
    return "\n".join(parts), detailed


def _score_framework(text: str, files: list[Path], d: Detection):
    low = text.lower()
    scores = {"v4": 0, "v5": 0}
    if "rlbot.agents.base_agent" in low:
        scores["v4"] += 7
        d.evidence.append("imports rlbot.agents.base_agent")
    if "gametickpacket" in low or "simplecontrollerstate" in low:
        scores["v4"] += 3
    if "[locations]" in low and "python_file" in low:
        scores["v4"] += 5
    if any(p.name.lower() == "rlbot.cfg" for p in files):
        scores["v4"] += 4
        d.configs.append("rlbot.cfg")

    if "from rlbot.managers import bot" in low or "rlbot.managers" in low:
        scores["v5"] += 7
        d.evidence.append("imports rlbot.managers (v5)")
    if "from rlbot import flat" in low or "rlbot.flat" in low:
        scores["v5"] += 4
    if "run_command_linux" in low or "#:schema https://rlbot.org/schemas/agent.json" in low:
        scores["v5"] += 5
    if any(p.name.lower().endswith("bot.toml") or p.name.lower() == "bot.toml" for p in files):
        scores["v5"] += 4

    if scores["v4"] and scores["v5"]:
        d.framework = "hybrid-v4-v5"
        d.framework_confidence = min(0.99, 0.70 + min(scores.values()) / 40)
        d.features.append("contains both v4 and v5 implementation signals")
    elif scores["v4"] > scores["v5"]:
        d.framework = "rlbot-v4"
        d.framework_confidence = min(0.99, 0.55 + scores["v4"] / 20)
    elif scores["v5"]:
        d.framework = "rlbot-v5"
        d.framework_confidence = min(0.99, 0.55 + scores["v5"] / 20)


def _detect_observation(text: str, d: Detection):
    low = text.lower()
    candidates: list[tuple[int, str, str]] = []

    def hit(score: int, name: str, reason: str):
        candidates.append((score, name, reason))

    if "nextoobsbuilder" in low or "nexto_obs" in low:
        hit(100, "NextoObsBuilder", "Nexto entity/QKV observation builder detected")
    if "nectoobsbuilder" in low or "necto_obs" in low:
        hit(100, "NectoObsBuilder", "Necto observation builder detected")
    if "relativeDefaultObs".lower() in low:
        hit(95, "RelativeDefaultObs", "RLGym RelativeDefaultObs detected")
    if re.search(r"\badvancedobs\b", low):
        hit(90, "AdvancedObs", "legacy RLGym AdvancedObs detected")
    if re.search(r"\bdefaultobs\b", low):
        hit(85, "DefaultObs", "RLGym DefaultObs detected")
    if "rlgym_rlbot" in low:
        hit(70, "RLGym-v2 custom/declared", "rlgym-rlbot wrapper detected")
        d.features.append("RLGym v2 RLBot wrapper")
    if "rlgym_compat" in low:
        hit(65, "RLGym-compat custom/declared", "rlgym_compat GameState detected")
        d.features.append("RLGym compat state conversion")
    if "obsbuilder" in low or "obs_builder" in low:
        hit(45, "custom ObsBuilder", "custom observation builder symbols detected")

    # Nexto's characteristic entity/QKV layout is distinctive even if renamed.
    if all(x in low for x in ("is_self", "is_mate", "is_opp", "is_ball", "is_boost")) and "batched_build_obs" in low:
        hit(98, "Nexto-like entity QKV", "Nexto-style entity selectors + batched_build_obs")

    if candidates:
        score, name, reason = max(candidates, key=lambda x: x[0])
        d.observation = name
        d.observation_confidence = score / 100
        d.observation_details = dict(OBS_PROFILES.get(name, {}))
        d.evidence.append(reason)

    action_patterns = [
        ("RepeatAction", r"\brepeataction\b"),
        ("LookupTableAction", r"\blookuptableaction\b"),
        ("LookupAction", r"\blookupaction\b"),
        ("ContinuousAction", r"\bcontinuousaction\b"),
        ("DiscreteAction", r"\bdiscreteaction\b"),
    ]
    found = [name for name, pat in action_patterns if re.search(pat, low)]
    if found:
        d.action_parser = "+".join(found[:2])
        d.features.append("action parser detected: " + d.action_parser)

    ticks = [int(x) for x in re.findall(r"tick_skip\s*=\s*(\d+)", low)]
    repeats = [int(x) for x in re.findall(r"repeats\s*=\s*(\d+)", low)]
    vals = ticks + repeats
    if vals:
        # Most projects use one stable tickskip; mode is more robust than first match.
        d.tick_skip = max(set(vals), key=vals.count)
        d.observation_details.setdefault("tick_skip", d.tick_skip)
        d.features.append(f"tick skip inferred: {d.tick_skip}")


def _detect_model(text: str, files: list[Path], d: Detection):
    low = text.lower()
    model_files = [
        str(p) for p in files
        if p.suffix.lower() in {".onnx", ".pt", ".pth", ".jit", ".tflite"}
    ]
    d.model_files = model_files[:40]

    runtimes = []
    if "onnxruntime" in low or any(x.lower().endswith(".onnx") for x in model_files):
        runtimes.append("ONNX Runtime")
    if "torch.jit" in low or "torch.load" in low or any(
        x.lower().endswith((".pt", ".pth", ".jit")) for x in model_files
    ):
        runtimes.append("PyTorch")
    if "tensorflow" in low or any(x.lower().endswith(".tflite") for x in model_files):
        runtimes.append("TensorFlow/TFLite")
    if "numpy" in low and not runtimes:
        runtimes.append("NumPy/custom")
    if runtimes:
        d.model_runtime = "+".join(runtimes)

    if "rlgym.api" in low or "rlgym.rocket_league" in low:
        d.features.append("RLGym v2 API")
    if "rlgym_sim" in low:
        d.features.append("RLGym-Sim training code")
    if "rocketSim".lower() in low:
        d.features.append("RocketSim references")


def _detect_configs(files: list[Path], detailed: list[tuple[Path, str]], d: Detection):
    seen = set(d.configs)
    for p, text in detailed:
        name = p.name.lower()
        if p.suffix.lower() == ".cfg" and "[locations]" in text.lower():
            if str(p) not in seen:
                d.configs.append(str(p))
                seen.add(str(p))
        elif name.endswith("bot.toml") or (
            p.suffix.lower() == ".toml" and "[settings]" in text.lower() and "run_command" in text.lower()
        ):
            if str(p) not in seen:
                d.configs.append(str(p))
                seen.add(str(p))
        if p.suffix.lower() == ".py":
            low = text.lower()
            if (
                "baseagent" in low
                or "rlbot.managers" in low
                or "rlgymbot" in low
            ):
                d.entrypoints.append(str(p))


def detect_bot(path: str | Path) -> dict:
    root = Path(path).expanduser().resolve()
    d = Detection()
    if not root.exists():
        d.warnings.append(f"path does not exist: {root}")
        return d.to_dict()

    files = list(dict.fromkeys(_iter_files(root)))
    text, detailed = _text_files(files)
    _score_framework(text, files, d)
    _detect_observation(text, d)
    _detect_model(text, files, d)
    _detect_configs(files, detailed, d)

    if not d.configs:
        d.warnings.append("no RLBot bot config detected")
    if d.observation == "unknown" and (
        "rlgym" in text.lower() or "obs" in text.lower()
    ):
        d.warnings.append("RLGym/observation code found but the observation layout is custom or unknown")
    if d.framework == "unknown":
        d.warnings.append("could not confidently identify RLBot v4 or v5")

    # Stable, concise ordering for diagnostics.
    d.features = list(dict.fromkeys(d.features))
    d.evidence = list(dict.fromkeys(d.evidence))
    d.entrypoints = list(dict.fromkeys(d.entrypoints))[:40]
    d.configs = list(dict.fromkeys(d.configs))[:40]
    return d.to_dict()
