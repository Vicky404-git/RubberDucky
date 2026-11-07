# RubberDucky — Phases 1–5 integration

This bundle is built on your earlier source and Phase 1–2 integration. It includes all five requested phases in one package.

## What's included

1. **Central configuration** — `src/core/config.py` loads `rubberducky.ini` once and shares Git, LLM, triage, voice, hotkey and logging settings.
2. **Ignore + safety manager** — `.gitignore` and `.rubberduckyignore` filtering, hard-coded sensitive-path exclusions, diff filtering, secret redaction, and approval-gated ignore suggestions.
3. **Parser cleanup** — one compact system prompt and one user prompt, validated JSON output, config-driven OpenRouter settings, explicit rate-limit/timeout/error fallbacks.
4. **Debug logging** — rotating root `debug.log`, timestamps, pipeline stages and timings. It intentionally logs metadata only, not transcripts, prompts, diffs, Docker logs, API keys or raw exception text.
5. **Git context** — read-only status, staged diff, unstaged diff, recent commits and merge-conflict detection. Context is ignore-filtered and redacted before reaching the LLM.

## Install into your existing repo

Extract this ZIP. From the extracted `rubberducky_phase1_5` directory, copy `src/`, `.rubberduckyignore`, and `README_PHASE1_5.md` into your repository. Review before overwriting files. **Keep your existing `rubberducky.ini`**; merge the `[logging]` section shown below rather than replacing your values.

```bash
uv add pathspec
uv sync
```

Add this to your existing `rubberducky.ini`:

```ini
[logging]
level = INFO
max_bytes = 1048576
backup_count = 3
```

Your existing `max_commits = 1` and `max_chars = 2000` are preserved and valid. Keep API keys in `.env`, never in the INI file.

## Run / verify

```bash
uv run python -m py_compile src/core/*.py src/api/*.py src/ducky.py src/manage_ignores.py
PYTHONPATH=src uv run python -m unittest discover -s tests -v
uv run python src/manage_ignores.py
uv run python src/ducky.py
```

Rebuild the X11 daemon after copying:

```bash
g++ -std=c++17 -O2 src/daemon/main.cpp -o ducky-daemon -lX11
```

`debug.log` is created on first logged event and rotated at the configured size. Add this to your existing `.gitignore` so Git itself ignores it (the bundle does not overwrite your existing file):

```gitignore
debug.log
debug.log.*
```

## Git features and safety

Git collection is read-only: it does not checkout, stage, commit, reset, merge, push or modify files. It gathers status, conflicts, staged/unstaged diffs and recent commit subjects. Ignore rules apply even to tracked files before AI context is built. Secret redaction is defense-in-depth, not a guarantee against every possible secret format.

## Before committing

```bash
git status --short
git diff --check
git diff -- src
```

Stage only intended source/docs/tests. Do not blindly stage `.env`, recordings, `debug.log`, or local credentials.
