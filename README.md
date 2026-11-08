# 🦆 RubberDucky

**A voice-native Linux debugging assistant.** Speak a development problem in Hindi/Hinglish, let RubberDucky transcribe it, classify the issue, gather safe repository context, request an evidence-aware diagnosis from an LLM, and hear the response through text-to-speech.

RubberDucky currently provides both a terminal workflow and a local browser-based interface. It is an assistant: it does not autonomously edit files, run model-generated shell commands, or guarantee that an LLM diagnosis is correct.

## What it does

1. **Capture** — record a short voice description using ALSA `arecord`.
2. **Transcribe** — use Gnani Prisma (`gnani-vachana`) to convert speech to text.
3. **Collect context** — read-only Git status, branch, conflicts, staged/unstaged diffs and recent commits; optionally collect Docker logs for infrastructure issues.
4. **Triage** — route the incident with the LAYA classifier and keyword rules.
5. **Diagnose** — send the sanitized transcript and relevant context to an OpenRouter model through the shared OpenAI-compatible client.
6. **Respond** — generate a concise diagnosis and Hinglish spoken response; use Gnani Timbre for audio output.
7. **Review** — inspect session history, Git context, logs, configuration and Ignore Manager suggestions in the local web UI.

## Current capabilities

| Area | Implementation |
|---|---|
| Voice input | Linux ALSA `arecord`; duration and language are configurable |
| Speech-to-text | Gnani Prisma through `gnani-vachana` |
| Triage | LAYA classifier with keyword routing and configurable CPU/CUDA device |
| Repository context | Read-only Git status, branch, merge conflicts, staged/unstaged diffs, recent commits and ignored paths |
| Infrastructure context | Docker log collection for infrastructure-classified issues when a container is supplied |
| LLM | Shared OpenRouter client with structured errors and JSON response validation |
| Speech output | Gnani Timbre REST adapter and local `aplay` playback |
| Local API | FastAPI bridge bound to `127.0.0.1:8756` |
| Web interface | React, TypeScript, Vite, Zustand, Tailwind and React Three Fiber orb |
| Sessions | Local session history, timeline, retry, playback and audio deletion |
| Ignore Manager | Suggests ignore patterns; applying changes requires explicit approval |
| Linux hotkey | C++ X11 daemon; default `Mod4+Alt+V` |

The web UI is a browser application served by the local FastAPI bridge. It is **not currently a Tauri/native desktop application**. The microphone is recorded by the local Python/ALSA process; raw microphone samples are not streamed into the browser.

## Architecture

```text
                 Linux desktop (X11)
        Super/Mod4 + Alt + V global hotkey
                         |
                  C++ X11 daemon
                         |
                  Python CLI adapter
                         |
        +----------------+----------------+
        |                                 |
  ALSA recording                     FastAPI bridge
        |                                 |
  Gnani Prisma STT                React/Vite browser UI
        |                           HTTP + WebSocket
        +----------------+----------------+
                         |
                  Shared core pipeline
                         |
       Git context -> LAYA triage -> Docker logs
                         |
               OpenRouter LLM client
                         |
              validated diagnosis JSON
                         |
                Gnani Timbre TTS
                         |
                  ALSA playback
```

### Main code areas

- `src/ducky.py` — CLI adapter, recording/STT, terminal output and playback.
- `src/core/pipeline.py` — shared Git → triage → optional Docker logs → LLM → TTS workflow.
- `src/core/git_ops.py` — structured, read-only Git context collection and formatting.
- `src/core/triage.py` — LAYA loading, keyword routing and classification.
- `src/core/llm_client.py` — shared OpenRouter client, JSON completion and typed errors.
- `src/core/parser.py` — diagnosis prompt, context sanitization and response validation.
- `src/core/repository.py` — bounded candidate-path scanning and common exclusions.
- `src/core/ignore.py` — ignore matching, diff filtering and sensitive-data sanitization.
- `src/api/stt.py`, `src/api/tts.py` — Gnani speech service adapters.
- `src/server/app.py` — local FastAPI routes, WebSocket events and static frontend serving.
- `src/server/session_runner.py`, `session_store.py`, `events.py` — session lifecycle, persistence and event delivery.
- `src/daemon/main.cpp` — configurable X11 global-hotkey daemon.
- `frontend/src/` — browser UI, typed API client, event connection, stores and components.

## Requirements

- Linux with an X11 session for the global-hotkey daemon. The CLI and browser bridge can be run without starting the daemon.
- Python 3.13+ and [`uv`](https://docs.astral.sh/uv/).
- Node.js and npm for frontend development/builds.
- X11 development headers and a C++17 compiler to build the daemon (`libx11-dev` on Debian/Ubuntu).
- ALSA utilities (`arecord`, `aplay`) and a working microphone/audio output.
- Gnani API access for Prisma STT and Timbre TTS.
- OpenRouter API key and access to the configured model.
- Docker only if you want the optional container-log context.

On Debian 13 / Ubuntu, the common system packages are:

```bash
sudo apt update
sudo apt install build-essential g++ libx11-dev libx11-6 alsa-utils
```

Check audio devices with `arecord -l` and `aplay -l`.

## Installation and configuration

```bash
git clone https://github.com/Vicky404-git/RubberDucky.git
cd RubberDucky
uv sync
cp .env.example .env
```

Edit `.env` locally:

```dotenv
GNANI_API=your_gnani_api_key
OPENROUTER_API_KEY=your_openrouter_api_key
```

Never commit `.env`, paste credentials into issues, or expose API keys in frontend code. The bridge returns credential-presence booleans only; provider keys remain in the Python process.

`rubberducky.ini` contains runtime settings. The checked-in defaults include:

```ini
[git]
max_commits = 1
max_chars = 2000

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

The application reads this file from the configured project root. Use the Settings page or edit the INI carefully; the bridge's config writer preserves comments and unrelated keys.

## Run the CLI

From the repository root:

```bash
uv run python src/ducky.py
```

The CLI records for the configured duration, transcribes speech, runs the shared debugging pipeline, prints the diagnosis and attempts local audio playback. It removes its temporary input/output audio files in its cleanup path.

## Run the web interface

### Development

Terminal 1 — start the local bridge:

```bash
uv run python src/server/app.py
```

Terminal 2 — start Vite:

```bash
cd frontend
npm ci
npm run dev
```

Open <http://127.0.0.1:5173>. Vite proxies `/api` and `/ws` to the bridge on `127.0.0.1:8756`.

### Production build

```bash
cd frontend
npm ci
npm run build
cd ..
uv run python src/server/app.py
```

Open <http://127.0.0.1:8756>. FastAPI serves `frontend/dist` when the build exists. The current WebSocket Origin allowlist and Vite proxy are configured for the default bridge port `8756`; if you change the port, update those settings together.

## Build and run the X11 hotkey daemon

Build from the repository root:

```bash
g++ -std=c++17 -O2 src/daemon/main.cpp -o ducky-daemon -lX11
./ducky-daemon
```

The daemon resolves the project root from its own executable location, reads `[hotkey]` from `rubberducky.ini`, and launches `.venv/bin/python src/ducky.py` when the configured shortcut is pressed. Keep the compiled `ducky-daemon` binary in the project root so that path resolution works. It requires an active X11 display; it is not a Wayland-native global shortcut implementation.

## Verification

From the repository root:

```bash
PYTHONPATH=src RUBBERDUCKY_STATE_DIR=/tmp/rd-test \
  uv run python -m unittest discover -s tests -v

PYTHONPATH=src uv run python -m py_compile \
  src/core/*.py src/api/*.py src/ducky.py src/manage_ignores.py \
  src/server/*.py tests/*.py
```

Frontend checks:

```bash
cd frontend
npm run typecheck
npm test
npm run build
```

Daemon compilation:

```bash
g++ -std=c++17 -O2 src/daemon/main.cpp -o /tmp/ducky-daemon-check -lX11
```

These commands verify local code/build behavior. They do not by themselves verify a real microphone, Gnani credentials, OpenRouter quota/model availability, TTS playback, or a complete desktop hotkey session. Those require manual testing in a configured Linux desktop environment.

## Security and operational boundaries

- The bridge binds to loopback (`127.0.0.1`) and validates local HTTP hosts. WebSocket event connections are restricted to the explicit local frontend Origin allowlist.
- API keys remain server-side; browser responses expose only whether credentials are configured.
- Git operations are read-only. RubberDucky does not stage, commit, reset, push or modify repository source files.
- Ignore Manager changes require explicit approval before writing ignore patterns.
- Git diffs and logs are filtered/sanitized before being included in model context or exposed to the UI. Do not intentionally speak secrets into the microphone.
- Session/audio data is stored locally in the configured state directory. Protect the local account and clean up stored data when no longer needed.
- LLM diagnoses are suggestions, not verified root causes. Validate recommendations against actual code, logs and tests before acting.

## Known limitations

- The current UI is browser-based; native Tauri packaging is not implemented.
- The global hotkey daemon uses X11 and is not a Wayland-native shortcut service.
- Speech and LLM features require valid external service credentials and network access.
- Browser autoplay policies may require a user interaction before audio playback.
- The listening orb animation is visual feedback; microphone audio is captured by ALSA rather than analyzed in-browser.
- A successful unit test or frontend build is not equivalent to a live microphone/STT/LLM/TTS end-to-end test.

## Contributing

Issues and focused pull requests are welcome. Before changing shared pipeline code, inspect its callers in both the CLI and FastAPI session runner. Keep provider credentials out of commits and bug reports.

Useful bug-report details include the OS/session type (X11 or Wayland), Python/Node versions, exact command, relevant sanitized logs, and a redacted configuration. Never attach `.env`, raw credentials, or unredacted private transcripts.

## License

No license has been specified in this repository yet. Until a license is added, reuse and redistribution should not be assumed to be permitted.

---

<p align="center">Built for developers who debug better by talking it out. 🦆</p>
