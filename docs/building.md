# Building

The source tree deliberately excludes large, third-party binaries.

## Linux

Developed on Fedora with Python 3.12, Qt Widgets and RLBot v5.

    ./setup-env.sh
    ./evilrlbot-ui

The setup script installs local venvs, obtains the native RLBotServer binary from the RLBot upstream release, and runs local smoke tests. It is not an unattended installation service; inspect it and run it in a fresh checkout.

For an AppImage, the packaging script expects a working local `.venv`, `.venv-v4`, `RLBotServer` and the external AppImage tooling. `packaging/build-appimage.sh` stages a clean runtime and builds the x86_64 artifact.

## Windows

The Windows port uses explicit overlays for source files with Windows-specific paths and process management.

    py -3.12 scripts/prepare_windows_source.py

This assembles `build/windows-source/`. You still need:

- Embedded or installable Windows Python runtimes for RLBot v4 and v5.
- Compatible wheels for the bundled runtimes.
- The native RLBotServer executable.
- A C compiler for `packaging/windows/launcher.c` and NSIS for the installer.

The packaged-release scripts expect these assets at specific paths in the assembled working directory. They are maintained for release builders, not intended to fetch or distribute the game.

The repository's `packaging/windows/test_bridge_from_bot_cwd.py` checks a previous regression where a v4 agent was started from a third-party bot directory and failed to import the application package.

## Tests

    python -m compileall -q ui src common v4_runtime tests
    python scripts/prepare_windows_source.py

With fully installed RLBot/Qt environments:

    .venv/bin/python -m unittest discover -s tests -p 'test_*.py'

Windows integration tests require Windows interpreters and a built release tree. Full match tests additionally require Rocket League. Passing source compilation alone does not validate in-game behavior.
