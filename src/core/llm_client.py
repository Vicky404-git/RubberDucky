"""Shared multi-provider LLM client and structured LLM failures.

Both incident diagnosis and ignore-pattern suggestions use this module so the
base URL, credentials, timeout, retry policy, and model settings are defined
once per provider through the registry in ``core.providers``. Error
classification is typed; callers must never branch on message text.
"""
from __future__ import annotations

import json
import os
import time
from enum import Enum
from typing import Any

from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    OpenAI,
    RateLimitError,
)

from core.config import AppConfig, load_config
from core.debuglog import log_event
from core.providers import ProviderSpec, get_provider

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
MAX_RETRIES = 0


class LLMErrorCode(str, Enum):
    MISSING_CREDENTIALS = "missing_credentials"
    UNSUPPORTED_PROVIDER = "unsupported_provider"
    EMPTY_TRANSCRIPT = "empty_transcript"
    RATE_LIMITED = "rate_limited"
    TIMEOUT = "timeout"
    CONNECTION_ERROR = "connection_error"
    AUTHENTICATION_ERROR = "authentication_error"
    PAYMENT_REQUIRED = "payment_required"
    SERVER_ERROR = "server_error"
    HTTP_ERROR = "http_error"
    EMPTY_RESPONSE = "empty_response"
    INVALID_JSON = "invalid_json"
    SCHEMA_ERROR = "schema_error"
    UNEXPECTED_ERROR = "unexpected_error"


class LLMError(Exception):
    """A structured, UI-safe LLM failure."""

    def __init__(
        self,
        code: LLMErrorCode,
        message: str,
        *,
        retryable: bool,
        status_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable
        self.status_code = status_code

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "code": self.code.value,
            "message": self.message,
            "retryable": self.retryable,
        }
        if self.status_code is not None:
            payload["status_code"] = self.status_code
        return payload


def _provider_spec(provider_id: str) -> ProviderSpec:
    spec = get_provider(provider_id)
    if spec is None or spec.kind != "llm":
        raise LLMError(
            LLMErrorCode.UNSUPPORTED_PROVIDER,
            f"The '{provider_id}' LLM provider is not supported. "
            "Update the provider in Settings.",
            retryable=False,
        )
    return spec


def get_api_key(provider_id: str | None = None) -> str | None:
    """Return the provider's key from the environment, never from config."""
    provider = provider_id or load_config().llm.provider
    spec = _provider_spec(provider)
    value = os.getenv(spec.env_var, "").strip()
    return value or None


def build_client(config: AppConfig | None = None) -> OpenAI:
    """Build the OpenAI-compatible client for the selected provider."""
    cfg = config or load_config()
    spec = _provider_spec(cfg.llm.provider)
    api_key = get_api_key(spec.id)
    if not api_key:
        raise LLMError(
            LLMErrorCode.MISSING_CREDENTIALS,
            f"{spec.name} is selected but {spec.env_var} is not configured. "
            "Add the key in Settings or .env and retry.",
            retryable=False,
        )
    return OpenAI(
        base_url=spec.base_url,
        api_key=api_key,
        timeout=float(cfg.llm.timeout),
        max_retries=MAX_RETRIES,
    )


def _status_error(status_code: int, spec: ProviderSpec) -> LLMError:
    if status_code == 401:
        return LLMError(
            LLMErrorCode.AUTHENTICATION_ERROR,
            f"{spec.name} rejected the API key (HTTP 401). "
            f"Check {spec.env_var} in Settings.",
            retryable=False,
            status_code=status_code,
        )
    if status_code == 402:
        return LLMError(
            LLMErrorCode.PAYMENT_REQUIRED,
            f"{spec.name} requires credits or payment (HTTP 402). "
            "Add credits or choose another model.",
            retryable=False,
            status_code=status_code,
        )
    if status_code == 429:
        return LLMError(
            LLMErrorCode.RATE_LIMITED,
            f"{spec.name} returned HTTP 429 (rate limited). Wait a moment, then retry.",
            retryable=True,
            status_code=status_code,
        )
    if status_code >= 500:
        return LLMError(
            LLMErrorCode.SERVER_ERROR,
            f"{spec.name} is temporarily unavailable (HTTP {status_code}). Retry the session.",
            retryable=True,
            status_code=status_code,
        )
    return LLMError(
        LLMErrorCode.HTTP_ERROR,
        f"{spec.name} returned HTTP {status_code}. Check the configured model or retry.",
        retryable=status_code in {408, 409, 425},
        status_code=status_code,
    )


def _raise_mapped(exc: Exception, started: float, spec: ProviderSpec) -> None:
    elapsed = (time.perf_counter() - started) * 1000
    if isinstance(exc, LLMError):
        raise exc
    if isinstance(exc, RateLimitError):
        error = _status_error(429, spec)
        log_event("llm", "rate_limited", level="warning", duration_ms=elapsed, code=429)
    elif isinstance(exc, APITimeoutError):
        error = LLMError(
            LLMErrorCode.TIMEOUT,
            f"The {spec.name} request timed out. Retry the session.",
            retryable=True,
        )
        log_event("llm", "request_timeout", level="warning", duration_ms=elapsed)
    elif isinstance(exc, APIConnectionError):
        error = LLMError(
            LLMErrorCode.CONNECTION_ERROR,
            f"Could not reach {spec.name}. Check your network connection.",
            retryable=True,
        )
        log_event("llm", "connection_error", level="error", duration_ms=elapsed)
    elif isinstance(exc, APIStatusError):
        error = _status_error(exc.status_code, spec)
        log_event(
            "llm",
            "http_error",
            level="error",
            duration_ms=elapsed,
            code=exc.status_code,
        )
    else:
        error = LLMError(
            LLMErrorCode.UNEXPECTED_ERROR,
            f"An unexpected error occurred while contacting {spec.name}. Retry the session.",
            retryable=True,
        )
        log_event("llm", "unexpected_error", level="error", duration_ms=elapsed)
    raise error from exc


def extract_json_object(content: str | None) -> dict[str, Any]:
    """Parse a JSON object, tolerating a surrounding Markdown code fence."""
    if not isinstance(content, str) or not content.strip():
        raise LLMError(
            LLMErrorCode.EMPTY_RESPONSE,
            "The AI returned an empty response. Retry the session.",
            retryable=True,
        )
    text = content.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
        if text.endswith("```"):
            text = text[:-3].strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise LLMError(
            LLMErrorCode.INVALID_JSON,
            "The AI returned an unparseable response. Retry the session.",
            retryable=True,
        ) from exc
    if not isinstance(data, dict):
        raise LLMError(
            LLMErrorCode.SCHEMA_ERROR,
            "The AI response was not a JSON object. Retry the session.",
            retryable=True,
        )
    return data


def _create_completion(
    active_client: OpenAI,
    *,
    model: str,
    system_prompt: str,
    user_prompt: str,
    temperature: float,
    max_tokens: int,
    use_json_mode: bool,
) -> Any:
    kwargs: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if use_json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    return active_client.chat.completions.create(**kwargs)


def complete_json(
    system_prompt: str,
    user_prompt: str,
    *,
    config: AppConfig | None = None,
    client: OpenAI | None = None,
    model: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> dict[str, Any]:
    """Request a JSON object from the selected provider or raise a structured LLMError."""
    cfg = config or load_config()
    spec = _provider_spec(cfg.llm.provider)
    active_client = client or build_client(cfg)
    started = time.perf_counter()
    log_event("llm", "request_started")
    try:
        response = _create_completion(
            active_client,
            model=model or cfg.llm.model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=cfg.llm.temperature if temperature is None else temperature,
            max_tokens=cfg.llm.max_tokens if max_tokens is None else max_tokens,
            use_json_mode=spec.json_mode,
        )
    except Exception as exc:
        # Some models reject response_format JSON mode with HTTP 400 even
        # though the provider supports it. Retry once without JSON mode — the
        # shared prompt and fence-tolerant parser keep the contract. This
        # never switches providers and never fabricates a response.
        json_mode_rejected = (
            spec.json_mode
            and spec.json_mode_fallback
            and isinstance(exc, APIStatusError)
            and exc.status_code == 400
        )
        if json_mode_rejected:
            log_event(
                "llm",
                "json_mode_disabled",
                level="warning",
                duration_ms=(time.perf_counter() - started) * 1000,
            )
            try:
                response = _create_completion(
                    active_client,
                    model=model or cfg.llm.model,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    temperature=cfg.llm.temperature if temperature is None else temperature,
                    max_tokens=cfg.llm.max_tokens if max_tokens is None else max_tokens,
                    use_json_mode=False,
                )
            except Exception as retry_exc:
                _raise_mapped(retry_exc, started, spec)
        else:
            _raise_mapped(exc, started, spec)

    choices = getattr(response, "choices", None)
    if not choices:
        log_event(
            "llm",
            "empty_response",
            level="warning",
            duration_ms=(time.perf_counter() - started) * 1000,
        )
        raise LLMError(
            LLMErrorCode.EMPTY_RESPONSE,
            f"{spec.name} returned no response choices. Retry the session.",
            retryable=True,
        )

    content = getattr(getattr(choices[0], "message", None), "content", None)
    try:
        data = extract_json_object(content)
    except LLMError as exc:
        level = "warning" if exc.retryable else "error"
        log_event(
            "llm",
            exc.code.value,
            level=level,
            duration_ms=(time.perf_counter() - started) * 1000,
        )
        raise

    log_event(
        "llm",
        "request_succeeded",
        duration_ms=(time.perf_counter() - started) * 1000,
    )
    return data
