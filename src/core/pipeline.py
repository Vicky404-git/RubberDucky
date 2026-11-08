"""Shared debugging pipeline for the CLI and the frontend adapter.

The pipeline owns business logic from Git collection through TTS. Interfaces
pass an event callback for progress reporting and keep only their own concerns:
terminal prompts/playback for the CLI and WebSocket/session persistence for the
bridge.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from api.tts import synthesize_audio
from core.config import AppConfig, load_config
from core.context import get_docker_logs
from core.debuglog import log_event
from core.git_ops import (
    GitContext,
    collect_git_context,
    format_git_context,
    git_context_summary,
)
from core.ignore import IgnoreManager
from core.llm_client import LLMError
from core.parser import analyze_incident
from core.triage import triage_incident

EventCallback = Callable[[str, dict[str, Any]], None]


@dataclass(frozen=True)
class TriageOutcome:
    category: str
    source: str
    requires_logs: bool
    log_probability: float
    raw: dict[str, Any] = field(default_factory=dict, compare=False)


@dataclass(frozen=True)
class DiagnosisOutcome:
    diagnosis: str
    spoken_response: str


@dataclass
class PipelineResult:
    transcript: str
    git_context: GitContext | None = None
    git_text: str = ""
    triage: TriageOutcome | None = None
    docker_logs: str | None = None
    diagnosis: DiagnosisOutcome | None = None
    audio_path: Path | None = None
    error: LLMError | None = None
    tts_error: bool = False


def derive_triage(triage_result: dict[str, Any]) -> TriageOutcome:
    """Normalize the LAYA response into a typed outcome."""
    answers = triage_result.get("answers", {}) if isinstance(triage_result, dict) else {}
    answers = answers if isinstance(answers, dict) else {}
    category_meta = answers.get("issue_category", {})
    category_meta = category_meta if isinstance(category_meta, dict) else {}
    requires_meta = answers.get("requires_logs", {})
    requires_meta = requires_meta if isinstance(requires_meta, dict) else {}

    category = str(category_meta.get("choice", "unknown"))
    source = str(category_meta.get("source", "laya"))
    log_probability = float(requires_meta.get("noul", 0.0) or 0.0)
    requires_logs = category == "infrastructure" or log_probability >= 0.70
    return TriageOutcome(
        category=category,
        source=source,
        requires_logs=requires_logs,
        log_probability=log_probability,
        raw=triage_result if isinstance(triage_result, dict) else {},
    )


def run_triage(transcript: str, git_text: str) -> TriageOutcome:
    return derive_triage(triage_incident(transcript, git_text))


def collect_docker_logs(container_name: str | None) -> str | None:
    if not container_name or not container_name.strip():
        return None
    return get_docker_logs(container_name.strip())


def diagnose_incident(
    transcript: str,
    git_text: str,
    docker_logs: str | None,
    category: str,
    manager: IgnoreManager,
) -> DiagnosisOutcome:
    analysis = analyze_incident(
        transcript,
        git_diff=git_text,
        docker_logs=docker_logs or "",
        category=category,
    )
    diagnosis = manager.sanitize_context(str(analysis.get("diagnosis", "")))
    spoken = manager.sanitize_context(str(analysis.get("tts_response", "")))
    return DiagnosisOutcome(diagnosis=diagnosis, spoken_response=spoken)


def generate_tts(
    spoken_response: str,
    output_path: Path,
    config: AppConfig,
) -> Path | None:
    if synthesize_audio(
        spoken_response,
        output_path=str(output_path),
        language=config.voice.language,
    ):
        return output_path
    return None


def run_debug_pipeline(
    transcript: str,
    *,
    config: AppConfig | None = None,
    repo_path: str | Path | None = None,
    docker_container: str | None = None,
    docker_container_provider: Callable[[], str | None] | None = None,
    output_audio_path: str | Path | None = None,
    on_event: EventCallback | None = None,
    infrastructure_logs_only: bool = False,
) -> PipelineResult:
    """Run the shared Git → triage → logs → LLM → TTS pipeline once.

    LLM failures are returned as ``result.error`` instead of fabricated
    diagnoses. TTS failures are reported through ``result.tts_error``.
    """
    cfg = config or load_config()
    root = Path(repo_path).resolve() if repo_path else cfg.project_root
    manager = IgnoreManager(root)
    emit = on_event or (lambda _event_type, _payload: None)
    result = PipelineResult(transcript=transcript)

    stage_started = time.perf_counter()
    result.git_context = collect_git_context(root)
    result.git_text = format_git_context(
        result.git_context,
        max_chars=cfg.git.max_chars,
        repo_path=root,
    )
    summary = git_context_summary(result.git_context)
    log_event(
        "git",
        "context_collected",
        duration_ms=(time.perf_counter() - stage_started) * 1000,
    )
    emit(
        "git_context_collected",
        {
            "branch": result.git_context.branch,
            "summary": summary,
            "context": result.git_context,
            "git_text": result.git_text,
        },
    )

    stage_started = time.perf_counter()
    emit("triage_started", {})
    result.triage = run_triage(transcript, result.git_text)
    log_event(
        "triage",
        "completed",
        duration_ms=(time.perf_counter() - stage_started) * 1000,
    )
    emit(
        "triage_completed",
        {
            "category": result.triage.category,
            "category_source": result.triage.source,
            "log_probability": result.triage.log_probability,
            "requires_logs": result.triage.requires_logs,
        },
    )

    needs_logs = result.triage.requires_logs
    if infrastructure_logs_only:
        needs_logs = needs_logs and result.triage.category == "infrastructure"
    if needs_logs:
        container = docker_container
        if not container and docker_container_provider is not None:
            container = docker_container_provider()
        if container and container.strip():
            emit("docker_logs_started", {"container": container})
            result.docker_logs = collect_docker_logs(container)
            emit(
                "docker_logs_completed",
                {"available": bool(result.docker_logs)},
            )

    stage_started = time.perf_counter()
    emit("llm_started", {})
    try:
        result.diagnosis = diagnose_incident(
            transcript,
            result.git_text,
            result.docker_logs,
            result.triage.category,
            manager,
        )
    except LLMError as exc:
        result.error = exc
        log_event(
            "llm",
            "failed",
            level="warning",
            duration_ms=(time.perf_counter() - stage_started) * 1000,
            code=exc.status_code,
        )
        emit("llm_failed", exc.as_dict())
        return result
    log_event(
        "llm",
        "completed",
        duration_ms=(time.perf_counter() - stage_started) * 1000,
    )
    emit(
        "llm_completed",
        {
            "diagnosis": result.diagnosis.diagnosis,
            "spoken_response": result.diagnosis.spoken_response,
        },
    )

    stage_started = time.perf_counter()
    emit("tts_started", {})
    if output_audio_path is None:
        result.tts_error = True
        log_event("tts", "failed", level="warning")
        emit("tts_failed", {})
        return result

    audio_path = Path(output_audio_path)
    generated = generate_tts(result.diagnosis.spoken_response, audio_path, cfg)
    if generated is None:
        result.tts_error = True
        log_event(
            "tts",
            "failed",
            level="warning",
            duration_ms=(time.perf_counter() - stage_started) * 1000,
        )
        emit("tts_failed", {})
        return result

    result.audio_path = generated
    log_event(
        "tts",
        "completed",
        duration_ms=(time.perf_counter() - stage_started) * 1000,
    )
    emit("tts_completed", {"audio_path": generated})
    return result
