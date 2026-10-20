# Architecture

Evil RLBot uses one match manager (RLBot v5) and two agent execution paths.

### Native v5 agents

Native agents are started by RLBotServer with their own agent configuration. Dependency probing selects a compatible installed Python when possible; the bundled environment remains a fallback for packaged releases.

### RLBot v4 agents

A v4 `bot.cfg` is mapped to a generated v5 agent whose entry point is `src/v5_bridge.py`. The bridge starts `v4_runtime/worker.py` in a separate interpreter with the RLBot 1.68 API. The two processes exchange structured packets and controller values over authenticated localhost IPC. The Windows and Linux process launchers differ, but the packet translation is shared.

The worker reconstructs the v4 ctypes packet expected by `BaseAgent.get_output()`. It also provides the original agent lifecycle hooks and translates renderer, loadout, quick-chat, MatchComms and game-state calls back to the v5 frontend.

The worker is deliberately separate from v5: both frameworks publish the Python package name `rlbot` and must not shadow each other.

### Timing

At 120 Hz, one tick lasts about 8.33 ms. The bridge therefore keeps the current controller output as a fallback if a worker cannot respond in time.

Bridge diagnostics periodically report median and p95 round-trip latency, packet conversion time and worker response time. These numbers vary by machine, number of bots and model inference overhead.

Ball prediction contains hundreds of slices. Sending it on every tick caused avoidable allocations and serialization. It is now fetched only when an agent calls the registered v4 ball-prediction API, and cached for that tick. Set `EVILRLBOT_V4_EAGER_PREDICTION=1` to use the original eager path when diagnosing bot compatibility.

### Dependencies and data

The UI imports bots into the user's data directory rather than the application installation. Per-bot dependencies are checked before a match starts; compatible host interpreters and preinstalled ML packages are reused when possible. Python major/minor version and native-wheel ABI must match.

The repository contains source code, not bundled Python interpreters, PyTorch copies, game assets, imported bot packages, or model checkpoints. Windows release packaging assembles the Windows code overlay and adds the externally obtained runtimes and RLBotServer binary.

### Limitations

The bridge targets the public RLBot v4 agent API, not every private callback or external plugin. Some features are approximated when v5 does not expose an equivalent. A successful `ready` status means that an agent initialized, not that its policy has been benchmarked or behaves correctly in every game mode.
