"""Command-line entry points for ctrader.

Each module under `app.cli` is invokable via `python -m app.cli.<name>`.
The CLIs are deliberately thin — all real logic lives in `app/services/`
so the same code paths are exercised from FastAPI, scheduled jobs, and
the CLI alike.
"""
