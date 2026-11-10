"""Local-only HTTP/WebSocket bridge for the RubberDucky frontend.

Run from the repository root:
    uv run python src/server/app.py

The service binds to 127.0.0.1 only and reuses the existing pipeline. API keys
stay in the Python process and are exposed to JavaScript as booleans only.
"""
from __future__ import annotations

import asyncio
import os
import re
import shutil
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv

# Make the existing src/ package layout importable when running this file.
SRC_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = SRC_ROOT.parent
load_dotenv(PROJECT_ROOT / ".env")
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from core.config import load_config, reset_config_cache
from core.debuglog import log_event
from core.ignore import DEFAULT_SENSITIVE_PATTERNS, IgnoreManager
from core.providers import PROVIDERS
from core.repository import collect_candidate_paths

from server.config_writer import update_ini_values
from server.connection_test import ConnectionTestError, run_connection_test
from server.credential_store import (
    CredentialError,
    all_provider_metadata,
    provider_metadata,
    remove_credential,
    save_credential,
)
from server.events import event_bus
from server.git_service import build_git_context, current_branch
from server.models import (
    ConfigUpdate,
    HealthResponse,
    IgnoreApplyRequest,
    PlaybackUpdate,
    ProviderCredentialRequest,
    ProviderCredentialResponse,
    ProviderInfo,
    ProviderTestRequest,
    ProviderTestResult,
    ProvidersResponse,
    SafeConfig,
    SessionRecord,
    StartSessionRequest,
)
from server.session_runner import session_runner
from server.session_store import session_store, state_dir

import logging
import subprocess

logger = logging.getLogger(__name__)

_managed_daemon: subprocess.Popen | None = None


def _start_daemon() -> None:
    """Start the X11 hotkey daemon if it is not already running."""
    global _managed_daemon

    if _daemon_running():
        logger.info("RubberDucky daemon is already running.")
        return

    daemon_path = PROJECT_ROOT / "ducky-daemon"

    if not daemon_path.is_file():
        logger.warning("Daemon executable not found: %s", daemon_path)
        return

    if not os.access(daemon_path, os.X_OK):
        logger.warning("Daemon executable is not executable: %s", daemon_path)
        return

    if not os.environ.get("DISPLAY"):
        logger.warning(
            "DISPLAY is not set. Cannot start the X11 hotkey daemon."
        )
        return

    try:
        _managed_daemon = subprocess.Popen(
            [str(daemon_path)],
            cwd=str(PROJECT_ROOT),
            env=os.environ.copy(),
            stdin=subprocess.DEVNULL,
        )

        logger.info(
            "Started RubberDucky daemon (PID %s).",
            _managed_daemon.pid,
        )

    except OSError:
        _managed_daemon = None
        logger.exception("Failed to start RubberDucky daemon.")


def _stop_managed_daemon() -> None:
    """Stop only the daemon instance started by this bridge."""
    global _managed_daemon

    process = _managed_daemon
    _managed_daemon = None

    if process is None or process.poll() is not None:
        return

    logger.info("Stopping managed RubberDucky daemon (PID %s).", process.pid)

    try:
        process.terminate()
        process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        logger.warning("Daemon did not stop gracefully; killing it.")
        process.kill()
        process.wait()
    except OSError:
        logger.exception("Error while stopping RubberDucky daemon.")


def _refresh_daemon_after_credentials_change() -> None:
    """Refresh the bridge-owned daemon so it inherits updated API credentials.

    A daemon started outside this FastAPI process is deliberately not killed:
    its owner may be a user's session manager or terminal. In that case we
    warn that a manual restart is required for the hotkey process to inherit
    the newly saved environment.
    """
    global _managed_daemon

    if _managed_daemon is not None:
        _stop_managed_daemon()
        _start_daemon()
        return

    if _daemon_running():
        logger.warning(
            "Provider credentials changed, but ducky-daemon is externally managed. "
            "Restart that daemon manually so hotkey sessions inherit the new credentials."
        )
        return

    _start_daemon()


FRONTEND_DIST = PROJECT_ROOT / "frontend" / "dist"

# Keep this in sync with the explicit origins accepted by the HTTP CORS
# middleware. WebSocket connections do not pass through CORSMiddleware.
LOCAL_FRONTEND_ORIGINS = frozenset({
    "http://127.0.0.1:5173",
    "http://localhost:5173",
    "http://127.0.0.1:4173",
    "http://localhost:4173",
    "http://127.0.0.1:8756",
    "http://localhost:8756",
})


def _env_present(name: str) -> bool:
    return bool(os.getenv(name, "").strip())


def _daemon_running() -> bool:
    try:
        entries = list(Path("/proc").iterdir())
    except OSError:
        return False
    for entry in entries:
        if not entry.name.isdigit():
            continue
        try:
            comm = (entry / "comm").read_text(encoding="utf-8", errors="ignore").strip()
        except OSError:
            continue
        if comm == "ducky-daemon":
            return True
    return False


def _safe_config() -> SafeConfig:
    config = load_config()
    return SafeConfig(
        llm={
            "provider": config.llm.provider,
            "model": config.llm.model,
            "models": dict(config.llm.models),
            "temperature": config.llm.temperature,
            "max_tokens": config.llm.max_tokens,
            "timeout": config.llm.timeout,
        },
        voice={
            "record_seconds": config.voice.record_seconds,
            "language": config.voice.language,
        },
        git={
            "max_commits": config.git.max_commits,
            "max_chars": config.git.max_chars,
            "timeout": config.git.timeout,
        },
        triage={"device": config.triage.device, "lazy_load": config.triage.lazy_load},
        hotkey={"key": config.hotkey.key, "modifiers": config.hotkey.modifiers},
        logging={
            "level": config.logging.level,
            "max_bytes": config.logging.max_bytes,
            "backup_count": config.logging.backup_count,
        },
        ignore={
            "gitignore_path": str(config.project_root / ".gitignore"),
            "rubberduckyignore_path": str(config.project_root / ".rubberduckyignore"),
            "gitignore_exists": (config.project_root / ".gitignore").is_file(),
            "rubberduckyignore_exists": (config.project_root / ".rubberduckyignore").is_file(),
            "builtin_sensitive_patterns": list(DEFAULT_SENSITIVE_PATTERNS),
        },
        paths={
            "project_root": str(config.project_root),
            "config_path": str(config.config_path),
            "env_file_present": (config.project_root / ".env").is_file(),
            "state_dir": str(state_dir()),
            "frontend_dist": str(FRONTEND_DIST),
        },
    )


def _status_payload() -> dict:
    config = load_config()
    latest = session_store.latest()
    running = session_runner.is_running
    if running:
        state = latest.status if latest else "processing"
    elif latest and latest.status in {"speaking", "failed"}:
        state = latest.status
    else:
        state = "idle"
    return {
        "state": state,
        "active": running,
        "daemon_running": _daemon_running(),
        "project_name": config.project_root.name,
        "project_root": str(config.project_root),
        "branch": current_branch(config.project_root),
        "hotkey": {"key": config.hotkey.key, "modifiers": config.hotkey.modifiers},
        "credentials": {
            "openrouter": _env_present("OPENROUTER_API_KEY"),
            "groq": _env_present("GROQ_API_KEY"),
            "gnani": _env_present("GNANI_API"),
        },
        "latest_session": latest.model_dump() if latest else None,
        "last_diagnosis": latest.diagnosis if latest else None,
        "session_count": len(session_store.list(100)),
    }


@asynccontextmanager
async def lifespan(_: FastAPI):
    event_bus.bind_loop(asyncio.get_running_loop())

    # Recover sessions interrupted by a previous bridge process.
    for session in session_store.list(100):
        if session.status in {"listening", "processing"}:
            session.status = "failed"
            session.stage = "idle"
            session.error = (
                "The backend restarted before this session finished. Retry it."
            )
            session.retryable = True
            session.updated_at = __import__("time").time()
            session_store.upsert(session)

    # Automatically start the global X11 hotkey daemon.
    _start_daemon()

    try:
        yield
    finally:
        # Never stop a daemon that was already running before this bridge.
        _stop_managed_daemon()


app = FastAPI(
    title="RubberDucky Bridge",
    version="0.1.0",
    description="Local-only adapter over the existing RubberDucky Python pipeline.",
    lifespan=lifespan,
)


@app.exception_handler(RequestValidationError)
async def safe_validation_error_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    """Return validation errors without echoing submitted values or contexts.

    Pydantic's default error details may include the original ``input`` value.
    For credential requests that value can be an API key, so this handler only
    returns the location, message and error type. It intentionally omits both
    ``input`` and ``ctx`` for every request-validation error.
    """
    safe_errors: list[dict[str, object]] = []
    for error in exc.errors():
        location = list(error.get("loc", ()))
        is_api_key_error = "api_key" in location
        safe_errors.append(
            {
                "loc": location,
                "msg": (
                    "Invalid credential request."
                    if is_api_key_error
                    else str(error.get("msg", "Invalid request."))
                ),
                "type": str(error.get("type", "value_error")),
            }
        )

    return JSONResponse(status_code=422, content={"detail": safe_errors})

app.add_middleware(
    CORSMiddleware,
    allow_origins=sorted(LOCAL_FRONTEND_ORIGINS),
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type"],
)


@app.middleware("http")
async def local_host_guard(request, call_next):
    host = request.headers.get("host", "")
    hostname = host.rsplit(":", 1)[0] if host.count(":") == 1 else host
    if hostname not in {"127.0.0.1", "localhost", "::1", "testserver"}:
        return JSONResponse({"detail": "Local access only."}, status_code=403)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    config = load_config()
    return HealthResponse(
        project_root=str(config.project_root),
        config_path=str(config.config_path),
        has_openrouter_key=_env_present("OPENROUTER_API_KEY"),
        has_groq_key=_env_present("GROQ_API_KEY"),
        has_gnani_key=_env_present("GNANI_API"),
        git_available=shutil.which("git") is not None,
        arecord_available=shutil.which("arecord") is not None,
        aplay_available=shutil.which("aplay") is not None,
    )


@app.get("/api/status")
def status() -> dict:
    return _status_payload()


@app.get("/api/config", response_model=SafeConfig)
def get_config() -> SafeConfig:
    return _safe_config()


@app.put("/api/config", response_model=SafeConfig)
def put_config(update: ConfigUpdate) -> SafeConfig:
    config = load_config()
    mapping: list[tuple[str, str, str | int | float | bool]] = [
        ("llm", "provider", update.llm_provider),
        ("llm", "model", update.llm_model),
        ("llm", "groq_model", update.llm_groq_model),
        ("llm", "temperature", update.llm_temperature),
        ("llm", "max_tokens", update.llm_max_tokens),
        ("llm", "timeout", update.llm_timeout),
        ("voice", "language", update.voice_language),
        ("voice", "record_seconds", update.record_seconds),
        ("git", "max_commits", update.git_max_commits),
        ("git", "max_chars", update.git_max_chars),
        ("logging", "level", update.logging_level),
        ("hotkey", "key", update.hotkey_key),
        ("hotkey", "modifiers", update.hotkey_modifiers),
        ("triage", "device", update.triage_device),
        ("triage", "lazy_load", update.triage_lazy_load),
    ]
    updates: dict[tuple[str, str], str] = {}
    for section, key, value in mapping:
        if value is None:
            continue
        if isinstance(value, bool):
            updates[(section, key)] = "true" if value else "false"
        else:
            updates[(section, key)] = str(value)

    changed = update_ini_values(config.config_path, updates)
    reset_config_cache()
    load_config(reload=True)
    if changed:
        log_event("config", "updated")
        event_bus.publish(
            "config_updated",
            {"message": f"Updated {len(changed)} setting(s).", "changed": changed},
        )
    return _safe_config()


def _publish_credentials_updated(provider_id: str, configured: bool) -> None:
    """Broadcast safe credential metadata only (never key values)."""
    log_event("credentials", "saved" if configured else "removed")
    event_bus.publish(
        "credentials_updated",
        {
            "message": f"Provider '{provider_id}' is now "
            + ("configured." if configured else "not configured."),
            "provider": provider_id,
            "configured": configured,
        },
    )


@app.get("/api/settings/providers", response_model=ProvidersResponse)
def get_providers() -> ProvidersResponse:
    """Safe provider metadata: presence flags only, never key values."""
    config = load_config()
    return ProvidersResponse(
        providers=[
            ProviderInfo(**item) for item in all_provider_metadata(config)
        ],
        selected_llm=config.llm.provider,
    )


@app.post(
    "/api/settings/providers/credentials", response_model=ProviderCredentialResponse
)
def save_provider_credential(request: ProviderCredentialRequest) -> ProviderCredentialResponse:
    try:
        save_credential(request.provider, request.api_key)
    except CredentialError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    _refresh_daemon_after_credentials_change()
    _publish_credentials_updated(request.provider, True)
    return ProviderCredentialResponse(
        provider=ProviderInfo(**provider_metadata(request.provider))
    )


@app.delete(
    "/api/settings/providers/credentials/{provider}",
    response_model=ProviderCredentialResponse,
)
def delete_provider_credential(provider: str) -> ProviderCredentialResponse:
    cleaned = provider.strip().lower()
    if cleaned not in PROVIDERS:
        raise HTTPException(status_code=404, detail="Unknown provider.")
    try:
        remove_credential(cleaned)
    except CredentialError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    _refresh_daemon_after_credentials_change()
    _publish_credentials_updated(cleaned, False)
    return ProviderCredentialResponse(
        provider=ProviderInfo(**provider_metadata(cleaned))
    )


@app.post("/api/settings/providers/test", response_model=ProviderTestResult)
def test_provider(request: ProviderTestRequest) -> ProviderTestResult:
    config = load_config()
    metadata = provider_metadata(request.provider, config)
    model = metadata["model"] if metadata["kind"] == "llm" else None
    try:
        result = run_connection_test(request.provider, model)
    except ConnectionTestError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ProviderTestResult(**result)


@app.get("/api/git/context")
def git_context() -> dict:
    try:
        return build_git_context(load_config().project_root)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Git context unavailable ({type(exc).__name__}).")


@app.get("/api/git/diff")
def git_diff(kind: str = "unstaged") -> dict:
    if kind not in {"staged", "unstaged"}:
        raise HTTPException(status_code=400, detail="kind must be 'staged' or 'unstaged'.")
    context = build_git_context(load_config().project_root)
    diff = context["staged_diff"] if kind == "staged" else context["unstaged_diff"]
    return {
        "kind": kind,
        "diff": diff,
        "empty": not diff or diff.startswith("No "),
        "length": len(diff),
        "redacted": True,
    }


def _ignore_payload() -> dict:
    config = load_config()
    manager = IgnoreManager(config.project_root)
    candidates = collect_candidate_paths(config.project_root, manager)
    suggestions = manager.suggest_patterns(candidates)
    preview = manager.preview_suggestions(suggestions)
    return {
        "gitignore": {
            "path": str(manager.gitignore_path),
            "exists": manager.gitignore_path.is_file(),
            "rules": manager.git_patterns,
        },
        "rubberduckyignore": {
            "path": str(manager.rubberduckyignore_path),
            "exists": manager.rubberduckyignore_path.is_file(),
            "rules": manager.rubber_user_patterns,
        },
        "builtin_sensitive_patterns": list(DEFAULT_SENSITIVE_PATTERNS),
        "suggestions": suggestions,
        "preview": preview,
        "sensitive_findings": manager.sensitive_findings(candidates),
        "candidate_count": len(candidates),
    }


@app.get("/api/ignore/rules")
def ignore_rules() -> dict:
    return _ignore_payload()


@app.post("/api/ignore/apply")
def ignore_apply(request: IgnoreApplyRequest) -> dict:
    if not request.approved:
        raise HTTPException(
            status_code=400,
            detail="Ignore suggestions require explicit approval.",
        )
    config = load_config()
    manager = IgnoreManager(config.project_root)
    try:
        applied = manager.apply_suggestions(
            request.patterns,
            approved=True,
            destination=request.destination,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if applied:
        log_event("ignore", "updated")
        event_bus.publish(
            "ignore_updated",
            {
                "message": f"Applied {len(applied)} ignore pattern(s).",
                "patterns": applied,
                "destination": request.destination,
            },
        )
    return {"applied": applied, "destination": request.destination, **_ignore_payload()}


@app.get("/api/sessions")
def list_sessions(limit: int = 50) -> dict:
    records = session_store.list(limit)
    return {
        "sessions": [record.model_dump() for record in records],
        "count": len(records),
    }


@app.get("/api/sessions/{session_id}", response_model=SessionRecord)
def get_session(session_id: str) -> SessionRecord:
    record = session_store.get(session_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Session not found.")
    return record


@app.post("/api/sessions/start", response_model=SessionRecord, status_code=202)
def start_session(request: StartSessionRequest | None = None) -> SessionRecord:
    try:
        return session_runner.start(request.docker_container if request else None)
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/api/sessions/{session_id}/retry", response_model=SessionRecord, status_code=202)
def retry_session(session_id: str, request: StartSessionRequest | None = None) -> SessionRecord:
    if session_store.get(session_id) is None:
        raise HTTPException(status_code=404, detail="Session not found.")
    try:
        return session_runner.start(request.docker_container if request else None)
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/api/sessions/{session_id}/playback", response_model=SessionRecord)
def session_playback(session_id: str, update: PlaybackUpdate) -> SessionRecord:
    record = session_runner.playback(session_id, update.phase)
    if record is None:
        raise HTTPException(status_code=404, detail="Session not found.")
    return record


@app.get("/api/sessions/{session_id}/audio")
def session_audio(session_id: str):
    record = session_store.get(session_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Session not found.")
    path = session_store.audio_path(record.id)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Audio is not available for this session.")
    return FileResponse(
        path,
        media_type="audio/wav",
        filename=f"rubberducky-{record.id}.wav",
        headers={"Cache-Control": "no-store"},
    )


@app.post("/api/sessions/{session_id}/audio/delete")
def delete_session_audio(session_id: str) -> dict:
    record = session_store.get(session_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Session not found.")
    path = session_store.audio_path(record.id)
    try:
        if path.is_file():
            path.unlink()
    except OSError as exc:
        raise HTTPException(status_code=500, detail="Could not delete audio.") from exc
    record.audio_url = None
    session_store.upsert(record)
    return {"deleted": True}


@app.get("/api/events")
def recent_events(limit: int = 100) -> dict:
    events = event_bus.history()
    return {"events": events[-max(1, min(limit, 200)):]}


LOG_LINE_RE = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} \| (\w+) \| (.*)$")


@app.get("/api/logs")
def recent_logs(limit: int = 200) -> dict:
    config = load_config()
    path = config.project_root / "debug.log"
    if not path.is_file():
        return {"path": str(path), "entries": [], "exists": False}
    try:
        if path.stat().st_size > 2_000_000:
            text = path.read_text(encoding="utf-8", errors="replace")[-500_000:]
        else:
            text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {"path": str(path), "entries": [], "exists": False}
    manager = IgnoreManager(config.project_root)
    entries = []
    for line in text.splitlines()[-max(1, min(limit, 500)):]:
        safe = manager.sanitize_context(line)
        match = LOG_LINE_RE.match(safe)
        if match:
            entries.append({"level": match.group(1), "line": safe, "message": match.group(2)})
        else:
            entries.append({"level": "INFO", "line": safe, "message": safe})
    return {"path": str(path), "entries": entries, "exists": True}


@app.websocket("/ws/events")
async def websocket_events(websocket: WebSocket) -> None:
    # Browsers always send Origin for WebSocket handshakes. Reject missing,
    # opaque ("null"), malformed, and non-local origins before accepting so
    # an arbitrary website cannot read local session events. Non-browser
    # clients must deliberately supply one of the trusted local origins.
    origin = websocket.headers.get("origin")
    if origin not in LOCAL_FRONTEND_ORIGINS:
        await websocket.close(code=1008, reason="Untrusted WebSocket origin.")
        return

    await websocket.accept()
    queue = event_bus.subscribe()
    try:
        await websocket.send_json(
            {
                "type": "snapshot",
                "events": event_bus.history(),
                "status": _status_payload(),
            }
        )
        while True:
            event = await queue.get()
            await websocket.send_json(event)
    except (WebSocketDisconnect, RuntimeError, asyncio.CancelledError):
        pass
    finally:
        event_bus.unsubscribe(queue)


if (FRONTEND_DIST / "assets").is_dir():
    app.mount(
        "/assets",
        StaticFiles(directory=str(FRONTEND_DIST / "assets")),
        name="frontend-assets",
    )


@app.get("/{full_path:path}", include_in_schema=False)
def serve_frontend(full_path: str):
    if full_path.startswith(("api/", "ws/")):
        raise HTTPException(status_code=404, detail="Not found.")
    index = FRONTEND_DIST / "index.html"
    if not index.is_file():
        return JSONResponse(
            {
                "service": "rubberducky-bridge",
                "message": "Frontend build not found. Run `npm run build` in frontend/.",
                "api": "/api/health",
            }
        )
    candidate = (FRONTEND_DIST / full_path).resolve()
    try:
        candidate.relative_to(FRONTEND_DIST.resolve())
    except ValueError:
        raise HTTPException(status_code=404, detail="Not found.")
    if full_path and candidate.is_file():
        return FileResponse(candidate)
    return FileResponse(index)


def main() -> None:
    import uvicorn

    port = int(os.getenv("RUBBERDUCKY_BRIDGE_PORT", "8756"))
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")


if __name__ == "__main__":
    main()
