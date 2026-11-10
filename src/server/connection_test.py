"""Real backend-side provider connection tests for BYOK credentials.

Each test sends a tiny credential-only request (listing or key metadata) and
never transmits repository context, transcripts or prompts. Provider response
bodies are never relayed to the frontend because they can echo masked key
material; only clean, synthesized status messages are returned.
"""
from __future__ import annotations

import os
from typing import Any

import httpx

from core.debuglog import log_event
from core.providers import ProviderSpec, get_provider

TEST_TIMEOUT_SECONDS = 10.0


class ConnectionTestError(Exception):
    """A typed, UI-safe connection-test failure (never contains a key)."""


def _result(
    provider: str, ok: bool, message: str, model: str | None = None, model_ok: bool | None = None
) -> dict[str, Any]:
    return {
        "provider": provider,
        "ok": ok,
        "message": message,
        "model": model,
        "model_ok": model_ok,
    }


def _clean_status_message(spec: ProviderSpec, status_code: int) -> str:
    if status_code in {401, 403}:
        return f"{spec.name} rejected the API key (HTTP {status_code}). Check the saved key."
    if status_code == 429:
        return f"{spec.name} is rate limiting this key (HTTP 429). Wait a moment and retry."
    if status_code >= 500:
        return f"{spec.name} is temporarily unavailable (HTTP {status_code})."
    return f"{spec.name} returned HTTP {status_code} while checking the key."


def _request_json(url: str, api_key: str) -> tuple[int | None, dict | list | None, str | None]:
    """GET a JSON document; returns (status, data, transport_error_name)."""
    try:
        with httpx.Client(timeout=TEST_TIMEOUT_SECONDS) as client:
            response = client.get(url, headers={"Authorization": f"Bearer {api_key}"})
    except httpx.RequestError:
        return None, None, "network"
    if response.status_code != 200:
        return response.status_code, None, None
    try:
        return 200, response.json(), None
    except ValueError:
        return 200, None, "parse"


def _models_from_payload(payload: Any) -> list[str]:
    if not isinstance(payload, dict):
        return []
    entries = payload.get("data")
    if not isinstance(entries, list):
        return []
    models: list[str] = []
    for entry in entries:
        if isinstance(entry, dict) and isinstance(entry.get("id"), str):
            models.append(entry["id"])
    return models


def _check_llm_provider(spec: ProviderSpec, model: str) -> dict[str, Any]:
    api_key = os.getenv(spec.env_var, "").strip()
    if not api_key:
        return _result(
            spec.id,
            False,
            f"{spec.name} is not configured. Save an API key first.",
            model=model,
            model_ok=None,
        )

    if spec.base_url is None:
        raise ConnectionTestError(f"{spec.name} does not define a base URL.")

    # OpenRouter's /models endpoint is public and does not validate the key,
    # so authentication is verified against /key first.
    if spec.id == "openrouter":
        status, _data, transport = _request_json(f"{spec.base_url}/key", api_key)
        if transport == "network":
            return _result(
                spec.id, False,
                f"Could not reach {spec.name}. Check your network connection.",
                model=model,
            )
        if status != 200:
            return _result(
                spec.id, False, _clean_status_message(spec, status or 0), model=model
            )

    status, payload, transport = _request_json(f"{spec.base_url}/models", api_key)
    if transport == "network":
        return _result(
            spec.id,
            False,
            f"Could not reach {spec.name}. Check your network connection.",
            model=model,
        )
    if status != 200:
        return _result(
            spec.id, False, _clean_status_message(spec, status or 0), model=model
        )
    if transport == "parse" or payload is None:
        return _result(
            spec.id,
            True,
            f"{spec.name} accepted the API key, but its model catalog could not be "
            "read. Model availability is inconclusive; this check does not run inference.",
            model=model,
            model_ok=None,
        )

    models = _models_from_payload(payload)
    if model and not models:
        return _result(
            spec.id,
            True,
            f"{spec.name} accepted the API key, but its model catalog did not "
            f"confirm whether '{model}' is available. This check does not run inference.",
            model=model,
            model_ok=None,
        )
    if model and model not in models:
        return _result(
            spec.id,
            True,
            f"{spec.name} accepted the API key, but model '{model}' is not in its "
            f"current model catalog. Check the model ID.",
            model=model,
            model_ok=False,
        )
    if model:
        return _result(
            spec.id,
            True,
            f"{spec.name} accepted the API key and model '{model}' is listed in "
            "the model catalog. This check does not verify inference access.",
            model=model,
            model_ok=True,
        )
    return _result(
        spec.id,
        True,
        f"{spec.name} accepted the API key.",
        model=None,
        model_ok=None,
    )


def run_connection_test(provider_id: str, model: str | None = None) -> dict[str, Any]:
    """Verify a stored credential against the provider. Never returns secrets."""
    spec = get_provider(provider_id)
    if spec is None:
        raise ConnectionTestError(f"Unknown provider '{provider_id}'.")
    if not spec.connection_test:
        raise ConnectionTestError(
            f"{spec.name} has no safe credential-only check. Test it through the "
            "speech pipeline (record a session)."
        )
    if spec.kind == "llm":
        result = _check_llm_provider(spec, model or spec.default_model or "")
    else:
        raise ConnectionTestError(f"Connection tests are not implemented for {spec.name}.")
    log_event(
        "credentials",
        "test_succeeded" if result["ok"] else "test_failed",
        level="info" if result["ok"] else "warning",
    )
    return result
