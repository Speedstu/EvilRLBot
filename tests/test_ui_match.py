"""Regression tests for EvilRLBot's V4/V5 GUI match composer."""
from __future__ import annotations

import shutil
import unittest
from pathlib import Path

from rlbot.config import load_match_config

from ui.match_config import build_match, validate_setup

ROOT = Path(__file__).resolve().parents[1]
V4 = ROOT / "legacy_bot" / "bot.cfg"
V5 = ROOT / "tests" / "detection_v5"


class MatchComposerTests(unittest.TestCase):
    def setUp(self):
        self.paths = {"v4": str(V4), "v5": str(V5)}
        self.generated = []

    def tearDown(self):
        for p in self.generated:
            shutil.rmtree(p.parent, ignore_errors=True)

    def build(self, players, **kwargs):
        match = build_match({"players": players, **kwargs}, self.paths)
        self.generated.append(match)
        return match, load_match_config(match)

    def test_exact_v4_multiple_bots_v5_native_and_psyonix(self):
        lineup = [
            {"kind": "human", "team": 0},
            {"kind": "bot", "id": "v4", "team": 0},
            {"kind": "bot", "id": "v4", "team": 1},
            {"kind": "bot", "id": "v5", "team": 1},
            {"kind": "psyonix", "skill": "Allstar", "team": 1},
        ]
        file, config = self.build(
            lineup, map="Stadium_P", mode="Soccar",
            mutators={"boost_amount": "UnlimitedBoost", "match_length": "TenMinutes"},
            options={"skip_replays": False},
        )
        self.assertEqual(5, len(config.player_configurations))
        self.assertEqual(
            ["Human", "CustomBot", "CustomBot", "CustomBot", "PsyonixBot"],
            [type(p.variety).__name__ for p in config.player_configurations],
        )
        self.assertIn('boost_amount = "UnlimitedBoost"', file.read_text())
        import tomllib
        with file.open("rb") as f:
            cfg = tomllib.load(f)
        v4_cfgs = [Path(x["config_file"]) for x in cfg["cars"][1:3]]
        self.assertNotEqual(v4_cfgs[0], v4_cfgs[1])
        ids = []
        for p in v4_cfgs:
            with p.open("rb") as f:
                agent = tomllib.load(f)
            ids.append(agent["settings"]["agent_id"])
            self.assertTrue((p.parent / "run.sh").exists() or (p.parent / "player/run.sh").exists())
        self.assertEqual(2, len(set(ids)))

    def test_launcher_choices_are_supported_by_real_v5_parser(self):
        for launcher, expected in (
            ("Steam", "Steam"), ("Heroic", "Custom"),
            ("Legendary", "Custom"), ("NoLaunch", "NoLaunch"),
            ("OfflineLegendary", "NoLaunch")
        ):
            with self.subTest(launcher=launcher):
                file, config = self.build([{"kind": "human", "team": 0}], launcher=launcher)
                self.assertEqual(expected, str(config.launcher).rsplit(".", 1)[-1])
                if launcher in ("Heroic", "Legendary"):
                    self.assertEqual(launcher.lower(), config.launcher_arg)

    def test_native_v5_only(self):
        _, match = self.build([{"kind": "bot", "id": "v5", "team": 1}])
        self.assertEqual(1, len(match.player_configurations))

    def test_reject_invalid_players_and_settings(self):
        for broken in [
            [],
            [{"kind": "human", "team": 0}, {"kind": "human", "team": 1}],
            [{"kind": "bot", "id": "missing", "team": 1}],
            [{"kind": "bot", "id": "v4", "team": 3}],
            [{"kind": "other", "team": 1}],
        ]:
            with self.subTest(broken=broken), self.assertRaises(ValueError):
                validate_setup({"players": broken}, self.paths)
        valid = [{"kind": "human", "team": 0}]
        for mut in [{"gravity": "Unsafe"}, {"arbitrary": "Default"}]:
            with self.assertRaises(ValueError):
                validate_setup({"players": valid, "mutators": mut}, self.paths)
        with self.assertRaises(ValueError):
            validate_setup({"players": valid, "map": "../../../etc/passwd"}, self.paths)

    def test_legacy_match_not_single_bot(self):
        with self.assertRaisesRegex(ValueError, "complete rlbot.cfg"):
            build_match(
                {"players": [{"kind": "bot", "id": "v4", "team": 0}]},
                {"v4": str(ROOT / "legacy_bot" / "rlbot.cfg")},
            )


if __name__ == "__main__":
    unittest.main()
