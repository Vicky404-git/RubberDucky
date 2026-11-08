"""Typed request/response models for the local frontend bridge."""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

SessionStatus = Literal[
    "idle",
    "listening",
    "processing",
    "speaking",
    "completed",
    "failed",
]


class TimelineEntry(BaseModel):
    type: str
    message: str
    timestamp: float


class SessionRecord(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    started_at: float
    updated_at: float
    status: SessionStatus = "idle"
    stage: str = "idle"
    transcript: Optional[str] = None
    category: Optional[str] = None
    category_source: Optional[str] = None
    requires_logs: bool = False
    log_probability: float = 0.0
    git_branch: Optional[str] = None
    git_summary: Optional[str] = None
    diagnosis: Optional[str] = None
    spoken_response: Optional[str] = None
    error: Optional[str] = None
    retryable: bool = False
    audio_url: Optional[str] = None
    duration_ms: Optional[int] = None
    timeline: list[TimelineEntry] = Field(default_factory=list)


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    service: str = "rubberducky-bridge"
    version: str = "0.1.0"
    project_root: str
    config_path: str
    has_openrouter_key: bool
    has_gnani_key: bool
    git_available: bool
    arecord_available: bool
    aplay_available: bool


class SafeConfig(BaseModel):
    llm: dict
    voice: dict
    git: dict
    triage: dict
    hotkey: dict
    logging: dict
    ignore: dict
    paths: dict


class ConfigUpdate(BaseModel):
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None
    llm_temperature: Optional[float] = Field(default=None, ge=0.0, le=2.0)
    llm_max_tokens: Optional[int] = Field(default=None, ge=64, le=8192)
    llm_timeout: Optional[int] = Field(default=None, ge=3, le=180)
    voice_language: Optional[str] = None
    record_seconds: Optional[int] = Field(default=None, ge=1, le=60)
    git_max_commits: Optional[int] = Field(default=None, ge=1, le=50)
    git_max_chars: Optional[int] = Field(default=None, ge=500, le=100000)
    logging_level: Optional[str] = None
    hotkey_key: Optional[str] = None
    hotkey_modifiers: Optional[str] = None
    triage_device: Optional[str] = None
    triage_lazy_load: Optional[bool] = None

    @field_validator("llm_provider")
    @classmethod
    def _provider(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        if value.strip().lower() != "openrouter":
            raise ValueError("Only the OpenRouter provider is supported by the backend.")
        return "openrouter"

    @field_validator("llm_model", "hotkey_key")
    @classmethod
    def _single_line(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        cleaned = value.strip()
        if not cleaned or "\n" in cleaned or "\r" in cleaned or len(cleaned) > 200:
            raise ValueError("Value must be a single non-empty line (max 200 chars).")
        return cleaned

    @field_validator("voice_language")
    @classmethod
    def _language(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        cleaned = value.strip()
        import re

        if not re.fullmatch(r"[A-Za-z]{2,3}(?:-[A-Za-z]{2,4})?", cleaned):
            raise ValueError("Language must look like 'hi-IN' or 'en-US'.")
        return cleaned

    @field_validator("logging_level")
    @classmethod
    def _level(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        cleaned = value.strip().upper()
        if cleaned not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            raise ValueError("Unsupported logging level.")
        return cleaned

    @field_validator("hotkey_modifiers")
    @classmethod
    def _modifiers(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        import re

        tokens = [token.strip() for token in value.split("+") if token.strip()]
        allowed = {
            "mod1", "mod2", "mod3", "mod4", "mod5",
            "alt", "super", "win", "ctrl", "control", "shift",
        }
        if not tokens or any(token.lower() not in allowed for token in tokens):
            raise ValueError("Modifiers must be a '+'-joined list of Mod1..Mod5, Alt, Super, Ctrl or Shift.")
        return "+".join(tokens)

    @field_validator("triage_device")
    @classmethod
    def _device(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        cleaned = value.strip().lower()
        if cleaned not in {"cpu", "cuda"}:
            raise ValueError("Triage device must be 'cpu' or 'cuda'.")
        return cleaned


class IgnoreApplyRequest(BaseModel):
    patterns: list[str] = Field(min_length=1, max_length=50)
    destination: Literal["rubberducky", "git"] = "rubberducky"
    approved: bool = False

    @field_validator("patterns")
    @classmethod
    def _patterns(cls, values: list[str]) -> list[str]:
        cleaned: list[str] = []
        for raw in values:
            pattern = str(raw).strip()
            if not pattern:
                continue
            if "\n" in pattern or "\r" in pattern or len(pattern) > 200:
                raise ValueError("Ignore patterns must be single lines under 200 chars.")
            cleaned.append(pattern)
        if not cleaned:
            raise ValueError("At least one non-empty pattern is required.")
        return cleaned


class PlaybackUpdate(BaseModel):
    phase: Literal["started", "completed"]


class StartSessionRequest(BaseModel):
    docker_container: Optional[str] = Field(default=None, max_length=128)

    @field_validator("docker_container")
    @classmethod
    def _container(cls, value: Optional[str]) -> Optional[str]:
        if value is None or not value.strip():
            return None
        import re

        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", value.strip()):
            raise ValueError("Invalid Docker container name.")
        return value.strip()
