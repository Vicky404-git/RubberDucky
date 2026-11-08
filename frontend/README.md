# RubberDucky Web UI

A dark, voice-first interface for RubberDucky. The animated orb, session timeline,
Git viewer, Ignore Manager, Settings and Logs are all driven by the real Python
pipeline through a local FastAPI bridge — no mocked diagnoses, transcripts or
audio levels.

## Why React instead of Tauri

Tauri was the original packaging target, but this Debian 13 machine does not ship
`webkit2gtk-4.1`. The UI therefore runs as a normal web app served by the bridge.
If Tauri becomes available later, this frontend can be embedded without changing
the API contract.

## Stack

- React 18 + TypeScript (strict) + Vite 5
- Tailwind CSS + hand-built UI primitives
- Zustand for bridge state
- React Three Fiber + Three.js for the orb
- Vitest for utility tests

## Quick start

From the repository root, start the bridge (it loads `.env` and serves the built
SPA on `127.0.0.1:8756`):

```bash
uv run python src/server/app.py
```

For live development, start Vite in a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Open <http://127.0.0.1:5173>. Vite proxies `/api` and `/ws` to
`127.0.0.1:8756`, so the UI and bridge share an origin in both dev and
production.

### Production build

```bash
cd frontend
npm run build
```

Then run the bridge and open <http://127.0.0.1:8756>. The bridge serves
`frontend/dist` with SPA fallback and mounts `/assets`.

## Verification

```bash
cd frontend
npm run typecheck
npm test
npm run build
```

Backend bridge tests, from the repository root:

```bash
PYTHONPATH=src RUBBERDUCKY_STATE_DIR=/tmp/rd-test \
  .venv/bin/python -m unittest tests.test_frontend_bridge -v
```

## How the integration works

- `src/services/api.ts` — typed fetch client for the bridge.
- `src/services/events.ts` — auto-reconnecting WebSocket with exponential backoff.
- `src/stores/appStore.ts` — single Zustand store; events patch the active session
  and trigger a debounced status/session refresh.
- `src/hooks/usePlayback.ts` — plays `/api/sessions/{id}/audio` through an
  `AudioContext`, reports playback start/completion, and feeds the analyser RMS
  into the orb.
- `src/components/Orb/OrbScene.tsx` — custom shader sphere, rings and particles.
  Motion honours `prefers-reduced-motion`; WebGL failure falls back to a CSS orb.
- `src/pages/IgnoreManager.tsx` — suggestions must be explicitly selected and
  approved before `POST /api/ignore/apply` is called.

### Orb states

| Backend | Orb |
|---|---|
| `idle` / `completed` | idle |
| `listening` | listening |
| `processing` | processing |
| `speaking` | speaking |
| `failed` | error |

The speaking waveform uses real Web Audio amplitude. The listening waveform is a
timed animation and is labelled as such, because microphone samples stay inside
ALSA and are never exposed to JavaScript.

## Security boundaries

- The bridge binds to `127.0.0.1` and rejects non-local `Host` headers.
- API keys stay in the Python process. The UI receives only presence booleans.
- Config writes preserve comments and unmanaged keys; only changed fields are sent.
- Git access is read-only. The UI never stages, commits, resets or pushes.
- Ignore application requires `approved: true`. Sensitive paths are detected by
  path, not by reading their contents.
- API responses use `Cache-Control: no-store`; audio is served with `no-store`.
- Logs are sanitised in the bridge before reaching the browser.

## Known limitations

- Browser autoplay policy may require one click to enable audio; the playback bar
  shows an "Enable audio" action when this happens.
- `npm audit` reports dev-tool advisory chains in Vite/Vitest (esbuild, tinypool).
  These affect the local development/test tooling, not the production bundle.
  Track updates to Vite and Vitest rather than force-upgrading across majors.
- The web UI is desktop-first; mobile navigation works, but the orb and timelines
  are tuned for wide screens.
