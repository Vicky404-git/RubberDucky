"""Orchestrates one debug session through the shared Python pipeline.

This module is an adapter, not a reimplementation. Recording and STT happen
here because the bridge owns its input file; Git, triage, Docker logs, LLM and
TTS all run through core.pipeline. The adapter adds WebSocket events, session
persistence, status transitions and browser audio serving.
"""
from __future__ import annotations

import secrets
import threading
import time
from typing import Any

from api.stt import STTError, transcribe_audio
from core.config import load_config
from core.debuglog import log_event
from core.git_ops import current_branch
from core.ignore import IgnoreManager
from core.pipeline import run_debug_pipeline
from ducky import record_audio

from server.events import event_bus
from server.models import SessionRecord, TimelineEntry
from server.session_store import session_store, state_dir


class SessionRunner:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None

    @property
    def is_running(self) -> bool:
        thread = self._thread
        return bool(thread and thread.is_alive())

    def _record(self, session: SessionRecord, **updates: Any) -> SessionRecord:
        for key, value in updates.items():
            setattr(session, key, value)
        session.updated_at = time.time()
        return session_store.upsert(session)

    def _emit(
        self,
        session: SessionRecord,
        event_type: str,
        message: str,
        *,
        status: str | None = None,
        stage: str | None = None,
        **payload: Any,
    ) -> None:
        if status is not None:
            session.status = status  # type: ignore[assignment]
        if stage is not None:
            session.stage = stage
        session.updated_at = time.time()
        entry = TimelineEntry(type=event_type, message=message, timestamp=session.updated_at)
        session.timeline = (session.timeline + [entry])[-60:]
        session_store.upsert(session)
        event_bus.publish(
            event_type,
            {
                "session_id": session.id,
                "status": session.status,
                "stage": session.stage,
                "message": message,
                **payload,
            },
        )

    def _fail(
        self,
        session: SessionRecord,
        message: str,
        *,
        code: str,
        retryable: bool,
        stage: str,
        **payload: Any,
    ) -> None:
        session.error = message
        session.retryable = retryable
        self._emit(
            session,
            "session_failed",
            message,
            status="failed",
            stage=stage,
            code=code,
            retryable=retryable,
            **payload,
        )
        log_event("session", "failed", level="error")

    def _handle_pipeline_event(
        self,
        session: SessionRecord,
        event_type: str,
        payload: dict[str, Any],
    ) -> None:
        if event_type == "git_context_collected":
            summary = str(payload.get("summary", ""))
            branch = payload.get("branch")
            self._record(session, git_branch=branch, git_summary=summary)
            self._emit(
                session,
                "git_context_collected",
                f"Git context collected · {summary}",
                status="processing",
                stage="triage",
                branch=branch,
                summary=summary,
            )
        elif event_type == "triage_started":
            self._emit(
                session,
                "triage_started",
                "Running LAYA triage…",
                status="processing",
                stage="triage",
            )
        elif event_type == "triage_completed":
            category = str(payload.get("category", "unknown"))
            source = str(payload.get("category_source", "laya"))
            log_probability = float(payload.get("log_probability", 0.0) or 0.0)
            requires_logs = bool(payload.get("requires_logs", False))
            self._record(
                session,
                category=category,
                category_source=source,
                requires_logs=requires_logs,
                log_probability=log_probability,
            )
            self._emit(
                session,
                "triage_completed",
                f"LAYA classified this as {category.upper()}.",
                status="processing",
                stage="llm",
                category=category,
                category_source=source,
                log_probability=log_probability,
            )
        elif event_type == "docker_logs_started":
            container = payload.get("container", "")
            self._emit(
                session,
                "docker_logs_started",
                f"Collecting logs from {container}…",
                status="processing",
                stage="llm",
            )
        elif event_type == "docker_logs_completed":
            available = bool(payload.get("available", False))
            self._emit(
                session,
                "docker_logs_completed",
                "Docker logs collected." if available else "No Docker logs available.",
                status="processing",
                stage="llm",
            )
        elif event_type == "llm_started":
            self._emit(
                session,
                "llm_started",
                "Asking the LLM for a diagnosis…",
                status="processing",
                stage="llm",
            )
        elif event_type == "llm_completed":
            diagnosis = str(payload.get("diagnosis", ""))
            spoken = str(payload.get("spoken_response", ""))
            self._record(session, diagnosis=diagnosis, spoken_response=spoken)
            self._emit(
                session,
                "llm_completed",
                "Diagnosis ready.",
                status="processing",
                stage="tts",
                diagnosis=diagnosis,
            )
        elif event_type == "tts_started":
            self._emit(
                session,
                "tts_started",
                "Generating spoken response with Gnani Timbre…",
                status="processing",
                stage="tts",
            )

    def start(self, docker_container: str | None = None) -> SessionRecord:
        with self._lock:
            if self.is_running:
                raise RuntimeError("A debug session is already running.")
            config = load_config()
            now = time.time()
            session = SessionRecord(
                id=f"{time.strftime('%Y%m%d-%H%M%S')}-{secrets.token_hex(3)}",
                started_at=now,
                updated_at=now,
                status="listening",
                stage="recording",
                git_branch=current_branch(config.project_root),
            )
            session_store.upsert(session)
            event_bus.publish(
                "session_started",
                {
                    "session_id": session.id,
                    "status": session.status,
                    "stage": session.stage,
                    "message": "Debug session started.",
                },
            )
            self._thread = threading.Thread(
                target=self._run,
                args=(session.id, docker_container),
                name=f"rubberducky-session-{session.id}",
                daemon=True,
            )
            self._thread.start()
            return session

    def _run(self, session_id: str, docker_container: str | None) -> None:
        config = load_config()
        session = session_store.get(session_id)
        if session is None:
            return
        manager = IgnoreManager(config.project_root)
        started = time.perf_counter()
        input_audio = state_dir() / "audio" / f"{session.id}-input.wav"
        input_audio.parent.mkdir(parents=True, exist_ok=True)
        log_event("app", "started")

        try:
            self._emit(
                session,
                "recording_started",
                f"Recording for {config.voice.record_seconds}s — speak now.",
                status="listening",
                stage="recording",
                duration_seconds=config.voice.record_seconds,
            )
            stage_started = time.perf_counter()
            if not record_audio(str(input_audio), duration=config.voice.record_seconds):
                self._fail(
                    session,
                    "Microphone recording failed. Check that arecord and a microphone are available.",
                    code="recording_failed",
                    retryable=True,
                    stage="recording",
                )
                return
            log_event(
                "recording",
                "completed",
                duration_ms=(time.perf_counter() - stage_started) * 1000,
            )
            self._emit(
                session,
                "recording_completed",
                "Recording complete.",
                status="processing",
                stage="transcription",
            )

            stage_started = time.perf_counter()
            self._emit(
                session,
                "transcription_started",
                "Transcribing audio with Gnani Prisma…",
                status="processing",
                stage="transcription",
            )
            try:
                transcript = transcribe_audio(
                    str(input_audio), language=config.voice.language
                )
            except STTError as exc:
                log_event(
                    "stt",
                    "failed",
                    level="error",
                    duration_ms=(time.perf_counter() - stage_started) * 1000,
                )
                self._fail(
                    session,
                    str(exc),
                    code="stt_failed",
                    retryable=True,
                    stage="transcription",
                )
                return
            transcript = manager.sanitize_context(transcript)
            log_event(
                "stt",
                "completed",
                duration_ms=(time.perf_counter() - stage_started) * 1000,
            )
            self._record(session, transcript=transcript)
            self._emit(
                session,
                "transcription_completed",
                f"You said: {transcript}",
                status="processing",
                stage="triage",
                transcript=transcript,
            )

            result = run_debug_pipeline(
                transcript,
                config=config,
                repo_path=config.project_root,
                docker_container=docker_container,
                output_audio_path=session_store.audio_path(session.id),
                on_event=lambda event_type, payload: self._handle_pipeline_event(
                    session, event_type, payload
                ),
            )

            if result.error is not None:
                self._fail(
                    session,
                    result.error.message,
                    code=result.error.code.value,
                    retryable=result.error.retryable,
                    stage="llm",
                )
                return

            if result.diagnosis is None:
                self._fail(
                    session,
                    "The AI did not return a diagnosis. Retry the session.",
                    code="invalid_response",
                    retryable=True,
                    stage="llm",
                )
                return

            if result.tts_error or result.audio_path is None:
                self._fail(
                    session,
                    "Text-to-speech is unavailable right now. The diagnosis is still saved.",
                    code="tts_failed",
                    retryable=True,
                    stage="tts",
                    diagnosis=result.diagnosis.diagnosis,
                    spoken_response=result.diagnosis.spoken_response,
                )
                return

            audio_url = f"/api/sessions/{session.id}/audio"
            self._record(
                session,
                audio_url=audio_url,
                duration_ms=int((time.perf_counter() - started) * 1000),
            )
            self._emit(
                session,
                "tts_completed",
                "Spoken response ready. Playing locally in the app.",
                status="speaking",
                stage="playback",
                audio_url=audio_url,
            )
            event_bus.publish(
                "playback_ready",
                {
                    "session_id": session.id,
                    "audio_url": audio_url,
                    "status": "speaking",
                    "stage": "playback",
                    "message": "Playback ready.",
                },
            )
            log_event("app", "analysis_completed")
        except Exception as exc:  # Preserve the CLI's non-crashing behaviour.
            log_event("app", "unexpected_error", level="error")
            self._fail(
                session,
                f"Unexpected backend error ({type(exc).__name__}). Check the bridge logs.",
                code="unexpected_error",
                retryable=True,
                stage=session.stage,
            )
        finally:
            log_event("app", "finished")
            try:
                if input_audio.exists():
                    input_audio.unlink()
            except OSError:
                pass

    def playback(self, session_id: str, phase: str) -> SessionRecord | None:
        session = session_store.get(session_id)
        if session is None:
            return None
        if phase == "started":
            self._emit(
                session,
                "playback_started",
                "Playing spoken response.",
                status="speaking",
                stage="playback",
            )
        elif phase == "completed":
            self._record(
                session,
                status="completed",
                stage="idle",
                duration_ms=session.duration_ms
                or int((time.time() - session.started_at) * 1000),
            )
            self._emit(
                session,
                "playback_completed",
                "Response playback finished.",
                status="completed",
                stage="idle",
            )
        return session


session_runner = SessionRunner()
