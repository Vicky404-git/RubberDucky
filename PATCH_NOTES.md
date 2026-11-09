# RubberDucky patch notes

This source snapshot contains a focused pre-submission maintenance patch.

## Changes

- Added an explicit WebSocket `Origin` allowlist to the existing FastAPI `/ws/events` route. Missing, opaque, malformed, and untrusted origins are rejected with policy close code `1008` before the socket is accepted. Existing API routes and application lifecycle are preserved.
- Added WebSocket tests for a trusted local frontend origin, an untrusted origin, and a missing origin.
- Fixed session-history retry selection: when the backend returns the new session created by retry, the Sessions page clears its search filter and selects that returned session. Existing session detail UI remains intact.
- Changed Git context collection so an empty/failed `git status` result is not represented as a clean repository. It now reports an unavailable-context status and marks the context as not clean.
- Added a regression test for Git status failure.
- Rewrote the main README to describe the current CLI, shared pipeline, local FastAPI bridge, browser frontend, X11 daemon, setup, testing, security boundaries, and limitations.

## Verification performed in the patch workspace

- Python compilation: passed.
- C++17/X11 daemon compilation: passed.
- Python unit tests: 32 passed using temporary import stubs for provider SDKs omitted from the source archive. No live provider calls were made. Run the normal project test command in the fully provisioned development environment to verify against installed dependencies.
- Frontend typecheck, Vitest, and production build: not run because `node_modules` was not included in the source archive and the package registry was unavailable in offline mode. Run `npm ci`, then `npm run typecheck`, `npm test`, and `npm run build` locally.
- Live microphone, Gnani STT/TTS, OpenRouter and complete browser-to-audio workflow: not tested.

No commits or pushes were made.
