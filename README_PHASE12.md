# RubberDucky Phase 1 + 2 integration

This bundle adds a central INI configuration loader and an approval-gated ignore manager.

## 1. Install the one new dependency

From the RubberDucky project root:

```bash
uv add pathspec
uv sync
```

`pathspec` provides Git-compatible ignore matching, including directory patterns and negation rules. The code has a conservative fallback, but `pathspec` is recommended for correct `.gitignore` behavior.

## 2. Copy the files

Copy the `src/` directory from this bundle into your project, replacing the matching files. It contains:

- `src/core/config.py` (new)
- `src/core/ignore.py` (new)
- updated `src/core/context.py`, `parser.py`, `triage.py`
- updated `src/api/stt.py`, `tts.py`
- updated `src/ducky.py`
- `src/manage_ignores.py` (new interactive ignore manager)
- updated `src/daemon/main.cpp`

The `.rubberduckyignore` file is a starting template. Review it before committing.

## 3. Preserve and extend your existing rubberducky.ini

Do not overwrite your current values. Ensure these options exist:

```ini
[git]
max_commits = 2
max_chars = 4000
timeout = 10

[hotkey]
key = v
modifiers = Mod4+Alt

[llm]
provider = openrouter
model = liquid/lfm-3-1.7b:free
temperature = 0.1
max_tokens = 700
timeout = 25

[triage]
device = cpu
lazy_load = true

[voice]
record_seconds = 5
language = hi-IN
```

Your current `max_commits = 1` and `max_chars = 2000` are valid settings; change them only if you want two commits and a larger context window.

## 4. Rebuild the X11 daemon

Use your existing compile command if it differs. Example:

```bash
g++ -std=c++17 -O2 src/daemon/main.cpp -o ducky-daemon -lX11
```

The daemon now reads `[hotkey] key` and `[hotkey] modifiers` from the same INI file. Supported modifier tokens include `Mod1`-`Mod5`, `Alt`, `Super`, `Win`, `Ctrl`, and `Shift`.

## 5. Run AI ignore suggestions

```bash
uv run python src/manage_ignores.py
```

The tool sends only candidate file paths (not file contents) to the configured OpenRouter model. It displays suggestions, asks for a destination, and requires explicit `y` approval before appending anything. If the model is unavailable/rate-limited, deterministic local suggestions are used instead.

- `.rubberduckyignore`: exclude paths from RubberDucky's AI context only.
- `.gitignore`: Git ignore rules; note that already tracked files remain tracked.

## 6. Verify

```bash
uv run python -m py_compile src/core/*.py src/api/*.py src/ducky.py src/manage_ignores.py

git check-ignore -v .env recording.wav temp_input.wav

uv run python src/manage_ignores.py
./ducky-daemon
```

The integration filters ignored file sections from historical Git patches and redacts common credential formats before they reach the LLM. It also sanitizes Docker log context. This is defense-in-depth, not a guarantee that every proprietary or unusual secret format is detected; never commit real secrets and keep credentials in environment variables.
