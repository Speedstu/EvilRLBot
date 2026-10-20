# Automated releases

A push to the default branch, or a manual run of **Build and publish release**
in GitHub Actions, starts a Windows and Linux release build.

The workflow:

1. Reads the latest published releases and increments the last version number
   (for example, v2026.10.20.5 becomes v2026.10.20.6).
2. Downloads the most recent Windows portable ZIP and Linux AppImage as
   runtime baselines.
3. Overlays the current Git commit's Python and UI code onto those known-good
   distributions. The Windows variant uses `ports/windows/overrides`.
4. Recompiles the Windows native launcher and icon, then builds the portable ZIP and NSIS installer on a hosted Windows
   runner. Repackages Linux as an AppImage on a hosted Ubuntu runner.
5. Checks the Windows bridge import and process-ownership regressions, and
   performs the Linux AppImage runtime self-test.
6. **Only if both builds pass**, publishes the three artifacts in a GitHub
   Release on a tag referencing the exact commit.

The workflow requires no local PC, self-hosted runner or manually configured
access token. It uses the short-lived `GITHUB_TOKEN` with contents write
permission only in the final publishing job. Concurrent releases are
serialized.

## What is and is not rebuilt

Application source is rebuilt on both platforms. Linux native launchers, Python
runtimes, installed wheels and RLBotServer are **not rebuilt from scratch** on
each push: they are carried forward from the previous published distribution.
This avoids redownloading large ML dependencies and introducing environment
drift. Changes to native dependencies, pinned versions or
RLBotServer need an explicitly tested new baseline release.

No user bot packages, models, personal files or Rocket League assets are
bundled.

## Troubleshooting

The workflow logs and intermediate build artifacts are available from
[Actions](https://github.com/Speedstu/EvilRLBot/actions/workflows/release.yml).
A failed build must not create a release. Fix the issue and push again or
rerun the workflow manually; the next version is computed from the last
**published** release rather than a failed run.
