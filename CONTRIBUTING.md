# Contributing

Keep changes focused. A useful bug report includes the OS, game launcher, RLBot agent type (v4 or native v5), a minimal reproduction and a relevant log excerpt.

For bridge changes, test both initialization and in-game ticks. Please avoid increasing overhead on the hot path without profiling, and preserve the old v4 API behavior unless a limitation is documented. A worker that reports `ready` but fails later in `get_output` is still a regression.

Do not commit game files, imported third-party bot weights, logs, local Python environments or generated release folders. Redact usernames, credentials and authorization arguments from diagnostics.

Pull requests should briefly explain what changed and how it was tested. No template required.
