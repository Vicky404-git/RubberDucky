# 🦆 RubberDucky

**Voice-native developer debugging assistant for Linux.** Speak a bug or crash in Hinglish, let RubberDucky transcribe it with Gnani Prisma, inspect available Git context, ask an LLM to explain the issue, and hear a Hinglish response through Gnani Timbre.

> RubberDucky is an early-stage CLI prototype. It currently captures a short microphone recording, transcribes it, collects the current Git diff, generates a diagnosis, and synthesizes a spoken response. It does not yet perform autonomous debugging or apply code fixes.

## What it does

RubberDucky is designed to be a developer's voice-first debugging companion:

1. **Speak** — record a short voice description of a coding or backend issue.
2. **Transcribe** — send the WAV recording to Gnani Prisma STT.
3. **Gather context** — collect the current repository's uncommitted Git diff.
4. **Analyze** — send the transcript and available context to an LLM through OpenRouter.
5. **Respond** — print a diagnosis and generate a spoken Hindi/Hinglish response using Gnani Timbre.
6. **Play** — play the generated WAV audio locally.

The goal is to make debugging feel like explaining a problem to a teammate: describe what is going wrong, provide relevant context, and get a practical explanation back.

## Current implementation

| Capability | Status | Details |
|---|---|---|
| Microphone recording | Implemented | Uses Linux `arecord` for a short, fixed-duration WAV recording |
| Speech-to-text | Implemented | Gnani Prisma via `gnani-vachana`, configured for `hi-IN` |
| Git context | Implemented | Reads the current uncommitted `git diff` |
| LLM diagnosis | Implemented | OpenAI-compatible client pointed at OpenRouter |
| Hinglish response generation | Implemented | LLM returns `diagnosis` and `tts_response` fields |
| Text-to-speech | Implemented | Gnani Timbre v2.5 REST endpoint |
| Local audio playback | Implemented | Uses Linux `aplay` |
| Docker log collection | Helper exists | A collector is present, but the current main flow does not request a container or pass Docker logs to the analyzer |
| Markdown incident reports | Planned | Not yet written to report files |
| Automatic root-cause verification | Planned | Diagnoses are model-generated and must be checked against evidence |
| Applying code fixes | Not implemented | RubberDucky does not currently edit source files |

## Architecture

```text
                 ┌──────────────────────┐
                 │   Developer speaks  │
                 │     (Hinglish)       │
                 └──────────┬───────────┘
                            │
                            ▼
                 ┌──────────────────────┐
                 │ Microphone recording│
                 │  arecord → input.wav│
                 └──────────┬───────────┘
                            │
                            ▼
                 ┌──────────────────────┐
                 │ Gnani Prisma (STT)   │
                 │  audio → transcript │
                 └──────────┬───────────┘
                            │
             ┌──────────────┴──────────────┐
             ▼                             ▼
   ┌──────────────────┐         ┌─────────────────────┐
   │ Git context      │         │ Spoken complaint    │
   │ git diff         │         │ transcript          │
   └────────┬─────────┘         └──────────┬──────────┘
            └──────────────┬──────────────┘
                           ▼
                 ┌──────────────────────┐
                 │ OpenRouter LLM       │
                 │ diagnosis + Hinglish │
                 └──────────┬───────────┘
                            │
                 ┌──────────┴───────────┐
                 ▼                      ▼
       ┌──────────────────┐   ┌──────────────────┐
       │ Terminal output  │   │ Gnani Timbre TTS │
       │ diagnosis        │   │ response.wav     │
       └──────────────────┘   └────────┬─────────┘
                                       ▼
                              ┌──────────────────┐
                              │ aplay playback   │
                              └──────────────────┘
```

### Main components

- **Trigger / recording —** `src/ducky.py` records audio through the Linux ALSA `arecord` command.
- **STT adapter —** `src/api/stt.py` wraps Gnani Prisma transcription.
- **Context collector —** `src/core/context.py` collects the Git diff and provides a Docker logs helper.
- **Analysis engine —** `src/core/parser.py` sends the complaint and available context to an OpenRouter model and parses its JSON response.
- **TTS adapter —** `src/api/tts.py` sends the response text to Gnani Timbre and saves the returned WAV audio.

## Tech stack

| Layer | Technology |
|---|---|
| Language | Python 3.13+ |
| Project / dependency runner | uv |
| Speech-to-text | Gnani Prisma (`gnani-vachana`) |
| Text-to-speech | Gnani Timbre v2.5 |
| LLM gateway | OpenRouter |
| LLM client | OpenAI Python SDK |
| Audio recording | ALSA `arecord` |
| Audio playback | ALSA `aplay` |
| Environment configuration | python-dotenv |

## Requirements

- Linux with a working microphone and ALSA utilities.
- Python 3.13 or later.
- [uv](https://docs.astral.sh/uv/) installed.
- Gnani API access for Prisma STT and Timbre TTS.
- An OpenRouter API key and access to the configured model.
- Internet connectivity for the hosted speech and LLM APIs.

On Debian/Ubuntu, install the audio utilities:

```bash
sudo apt install alsa-utils
```

Check that the microphone is available:

```bash
arecord -l
```

Check that playback devices are available:

```bash
aplay -l
```

## Setup

Clone the repository and enter it:

```bash
git clone https://github.com/Vicky404-git/RubberDucky.git
cd RubberDucky
```

Install dependencies:

```bash
uv sync
```

Create your local environment file:

```bash
cp .env.example .env
```

Edit `.env` and provide your API credentials:

```dotenv
GNANI_API=your_gnani_api_key
OPENROUTER_API_KEY=your_openrouter_api_key
```

Keep the real `.env` file private. It is excluded through `.gitignore`; never commit API keys or paste them into issue reports.

The current parser reads `OPENROUTER_API_KEY`. The STT and TTS adapters read `GNANI_API`.

## Run

From the repository root:

```bash
uv run src/ducky.py
```

RubberDucky records for five seconds by default. Speak a concise description of the problem while recording.

Example:

> "Yaar, API crash ho rahi hai baar baar jab bhi naya user create karta hoon."

The application then transcribes the recording, reads the current Git diff, requests an LLM diagnosis, and attempts to play the generated voice response.

## Example output

The exact transcript and diagnosis depend on your audio, repository state, and the configured model.

```text
🦆 RubberDucky initializing...
🎙️ Recording for 5 seconds... Speak your Hinglish bug now!
✅ Recording complete.
👂 Transcribing audio with Prisma...

💬 You said: '...'

🔍 Gathering System Context...
--- Git Diff Snapshot ---
...

🧠 LLM Parsing Incident...

📝 --- INCIDENT DIAGNOSIS ---
...

🗣️ Speaking response: '...'
🔊 Playing response...
```

## Project structure

```text
RubberDucky/
├── .env.example
├── .gitignore
├── pyproject.toml
├── uv.lock
└── src/
    ├── ducky.py           # Main CLI pipeline and audio recording
    ├── api/
    │   ├── stt.py         # Gnani Prisma STT adapter
    │   └── tts.py         # Gnani Timbre TTS adapter
    └── core/
        ├── context.py     # Git diff and Docker log helpers
        └── parser.py      # OpenRouter-based incident analysis
```

## Safety and limitations

RubberDucky is an assistant, not an autonomous system administrator.

- Treat LLM diagnoses as suggestions, not verified root causes.
- A Git diff is only a snapshot of uncommitted tracked changes; it is not the complete project or runtime state.
- Do not assume that the model has inspected logs or files that were not supplied to it.
- The current main flow does not execute shell commands generated by the model or apply code changes.
- Review any suggested command or fix before running it.
- Avoid sending secrets, access tokens, credentials, or private data in transcripts and context.
- Audio files are temporary and the current script attempts to remove them after the run. An interrupted process may leave temporary files behind.

## Roadmap

- [ ] Add push-to-talk / configurable recording duration.
- [ ] Add robust API key validation, request timeouts, and clearer provider errors.
- [ ] Add user-selected, read-only Docker log collection to the main pipeline.
- [ ] Add scoped context selection so the user chooses which repository, container, or log file is inspected.
- [ ] Generate Markdown and JSON incident reports.
- [ ] Distinguish user-reported symptoms, collected evidence, and model hypotheses in every diagnosis.
- [ ] Add tests for parsing, context collection, and provider failures.
- [ ] Add optional Git history and selected log-file context.
- [ ] Add a safe, explicit workflow for proposing patches without silently modifying the working tree.
- [ ] Extract reusable speech and context interfaces for future integration with Clanka, Synthia, and SOZO.

## Design direction

RubberDucky follows a modular, CLI-first approach. Speech input/output, context collection, and diagnosis are separate components so they can evolve independently.

The longer-term goal is to make RubberDucky a voice interface that can integrate with the wider developer-tool ecosystem:

- **Clanka** — local code intelligence and retrieval.
- **Synthia** — voice and permission-aware tool integrations.
- **SOZO** — persistent knowledge, events, and timeline.

These are future integration directions, not runtime dependencies of the current prototype. RubberDucky should remain usable as a standalone project.

## Contributing

Contributions and practical feedback are welcome. Before proposing a feature, check the current implementation and roadmap so planned capabilities are not mistaken for existing ones.

For bug reports, include:

- The command you ran.
- The relevant error message or traceback.
- Your Python and operating-system versions.
- A redacted example of the relevant configuration (never include API keys).

## License

No license has been specified in this repository yet. Until a license is added, all rights remain with the copyright holder and reuse should not be assumed to be permitted.

---

<p align="center">
  Built for developers who debug better by talking it out. 🦆
</p>
