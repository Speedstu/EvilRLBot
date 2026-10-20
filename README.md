# Evil RLBot

A desktop launcher for Rocket League bots, built around the RLBot v5 engine with a separate compatibility worker for RLBot v4 agents.

Evil RLBot can import bot packages, build blue/orange teams, configure a match, and start it from a native Qt interface. V4 agents run against the original RLBot 1.68 Python API; a bridge translates packets and controls between v4 and v5.

## Download

Use the **Releases** page for a ready-to-run build.

- **Windows 10/11 (x64)**: installer or portable ZIP.
- **Linux (x86_64)**: AppImage. Rocket League must already be installed and configured through a supported launcher.

Windows builds have been exercised with the Epic Games version of Rocket League. The Linux AppImage has passed runtime self-tests, but game/launcher compatibility depends on the local Wine/Proton setup.

Evil RLBot does **not** include Rocket League, paid game content, third-party bot weights, or a way around game ownership.

## Usage

1. Open Evil RLBot.
2. Import a bot folder or package (`.zip`, `.7z`, `.rar`, `.cfg`, or `.toml`).
3. Place the bots on the blue and orange teams. A match can also include human players.
4. Select the arena, mode and launcher; press **Start Match**.

Bot-specific Python dependencies are checked before starting the match. Where possible, the launcher reuses a compatible Python installation already on the machine, including PyTorch. It does not silently replace your system packages. Dependencies and imported bots are kept outside the application directory.

Logs and diagnostics are available from the application menu.

## How it works

    RLBot v4 agent (bot.cfg / BaseAgent)
                 |
        Python worker / RLBot 1.68 API
                 |
       localhost IPC / packet adapter
                 |
        RLBot v5 agent frontend
                 |
            RLBotServer
                 |
            Rocket League

Native v5 agents run directly through RLBot v5 and do not use the compatibility worker.

The v4 bridge preserves the usual bot lifecycle, controls, game packets, loadouts, game-state requests, quick chat and rendering calls. Ball prediction is sent **on demand** rather than serialized on every frame; the worker caches it for the current tick. Compatibility isn't guaranteed for every private RLBot API or every third-party bot package.

There is a cost to crossing the v4/v5 boundary. The bridge logs per-bot median and p95 timing, and it will reuse the previous control if a worker stalls. The overlay's update percentage can therefore be below 100% on CPU-heavy models.

More detail: [Architecture](docs/architecture.md).

## Source tree

| Path | Purpose |
| --- | --- |
| `ui/` | Qt interface, imports, dependency checks and match setup (Linux base) |
| `src/v5_bridge.py` | v5-side packet and controller adapter |
| `v4_runtime/` | Actual RLBot v4 worker process |
| `common/` | Bot introspection and shared utilities |
| `ports/windows/overrides/` | Windows-specific variants of the affected modules |
| `packaging/` | Linux AppImage and Windows build scripts |
| `tests/` | Unit and integration tests |
| `legacy_bot/` | Small v4 example agent |

Windows and Linux differ in process management, launcher discovery and runtime paths. The Windows-specific modules are collected as overlays instead of duplicating the whole source tree.

## Developing

Python 3.12 is used for the bundled v5 runtime. The v4 worker requires RLBot 1.68 and a compatible Python installation. For Linux development:

    git clone https://github.com/Speedstu/EvilRLBot.git
    cd EvilRLBot
    ./setup-env.sh
    ./evilrlbot-ui

`setup-env.sh` downloads RLBotServer from the upstream RLBot release and creates local development environments. Review the script before running it. Building a release additionally requires the packaging tools described under `packaging/`.

For a Windows source workspace (without vendored runtimes):

    python scripts/prepare_windows_source.py

The result is written to `build/windows-source/`. You'll need the Windows Python runtimes, RLBotServer and an appropriate Windows toolchain to make an installer. See [Building](docs/building.md).

Basic source check:

    python -m compileall -q ui src common v4_runtime tests
    python scripts/prepare_windows_source.py

Integration tests require the matching RLBot dependencies and, for game-launch tests, a Rocket League installation.

## Scope

Evil RLBot is a community project, not an official RLBot or Psyonix/Epic Games product. Reports about specific bots should include the agent config, dependency versions, application logs and whether the agent uses the v4 bridge or the native v5 path. Please remove tokens and personal paths from logs before posting.

MIT license; see [LICENSE](LICENSE). RLBot and other third-party components retain their respective notices.
