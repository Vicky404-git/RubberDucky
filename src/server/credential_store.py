"""Secure BYOK credential management for the local bridge.

Credentials are stored in the project-root ``.env`` file — local plaintext
protected by filesystem permissions (0600), not encrypted storage. Writes are
atomic (temporary file + ``os.replace``) and preserve unrelated environment
variables, comments and ordering. Saved keys are also written into the running
process environment so subsequent requests use them without a restart; shell-
exported variables still take precedence on a fresh start because
``load_dotenv()`` does not override existing values.

API keys never leave this module's return values: every public helper returns
safe metadata only (provider id, configured flag). Values are never logged.
"""
from __future__ import annotations

import os
import re
import stat
import tempfile
import threading
from pathlib import Path

from core.config import PROJECT_ROOT, AppConfig, load_config
from core.providers import PROVIDERS, ProviderSpec, get_provider

# Overridable for tests so the real project .env is never touched.
ENV_FILE_OVERRIDE: Path | None = None

_KEY_RE = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=")
_SAFE_VALUE_RE = re.compile(r"^[A-Za-z0-9_\-.,:/+=@]+$")
MAX_KEY_LENGTH = 512

# Protect the read/modify/replace transaction from concurrent API requests.
_ENV_FILE_LOCK = threading.RLock()


class CredentialError(Exception):
    """A typed, UI-safe credential failure (never contains a key value)."""


def _env_path() -> Path:
    return ENV_FILE_OVERRIDE if ENV_FILE_OVERRIDE is not None else PROJECT_ROOT / ".env"


def _require_spec(provider_id: str) -> ProviderSpec:
    spec = get_provider(provider_id)
    if spec is None:
        raise CredentialError(f"Unknown provider '{provider_id}'.")
    return spec


def validate_api_key(value: str) -> str:
    """Reject empty, multi-line or oversized values. Returns the cleaned key."""
    cleaned = value.strip()
    if not cleaned:
        raise CredentialError("The API key cannot be empty.")
    if len(cleaned) > MAX_KEY_LENGTH:
        raise CredentialError(f"The API key is too long (max {MAX_KEY_LENGTH} characters).")
    if any(character in cleaned for character in "\n\r\t\x00"):
        raise CredentialError("The API key must be a single line without control characters.")
    return cleaned


def _format_value(value: str) -> str:
    if _SAFE_VALUE_RE.match(value):
        return value
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _write_env_atomic(path: Path, text: str) -> None:
    """Write the .env file atomically with restrictive 0600 permissions."""
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        prefix=".rubberducky-env-", suffix=".tmp", dir=str(path.parent)
    )
    try:
        os.fchmod(descriptor, stat.S_IRUSR | stat.S_IWUSR)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(text)
        os.replace(temporary, path)
    except Exception:
        try:
            os.close(descriptor)
        except OSError:
            pass
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def _apply_env_var(env_var: str, value: str | None) -> None:
    """Update (or remove) the variable in the running process environment."""
    if value is None:
        os.environ.pop(env_var, None)
    else:
        os.environ[env_var] = value


def is_configured(provider_id: str) -> bool:
    spec = _require_spec(provider_id)
    return bool(os.getenv(spec.env_var, "").strip())


def save_credential(provider_id: str, api_key: str) -> dict:
    """Persist a credential to .env and the runtime environment.

    Duplicate assignments for the same provider variable are collapsed into
    one canonical assignment. The key value is never returned.
    """
    spec = _require_spec(provider_id)
    value = validate_api_key(api_key)
    path = _env_path()

    with _ENV_FILE_LOCK:
        lines: list[str] = []
        if path.is_file():
            try:
                lines = path.read_text(encoding="utf-8").splitlines()
            except OSError as exc:
                raise CredentialError("Could not read the existing .env file.") from exc

        assignment = f"{spec.env_var}={_format_value(value)}"
        output: list[str] = []
        inserted = False
        for line in lines:
            match = _KEY_RE.match(line)
            if match and match.group(1) == spec.env_var:
                if not inserted:
                    output.append(assignment)
                    inserted = True
                # Skip any later duplicate so dotenv cannot select a stale key.
                continue
            output.append(line)

        if not inserted:
            if output and output[-1].strip():
                output.append("")
            output.append(assignment)

        try:
            _write_env_atomic(path, "\n".join(output).rstrip() + "\n")
        except OSError as exc:
            raise CredentialError("Could not write the .env file.") from exc

        _apply_env_var(spec.env_var, value)

    return {"provider": spec.id, "configured": True}


def remove_credential(provider_id: str) -> dict:
    """Remove all assignments for a credential from .env and runtime env."""
    spec = _require_spec(provider_id)
    path = _env_path()

    with _ENV_FILE_LOCK:
        if not path.is_file():
            _apply_env_var(spec.env_var, None)
            return {"provider": spec.id, "configured": False}

        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError as exc:
            raise CredentialError("Could not read the existing .env file.") from exc

        kept = [
            line
            for line in lines
            if not (match := _KEY_RE.match(line)) or match.group(1) != spec.env_var
        ]
        if len(kept) != len(lines):
            try:
                _write_env_atomic(path, "\n".join(kept).rstrip() + "\n")
            except OSError as exc:
                raise CredentialError("Could not write the .env file.") from exc

        _apply_env_var(spec.env_var, None)

    return {"provider": spec.id, "configured": False}


def provider_metadata(provider_id: str, config: AppConfig | None = None) -> dict:
    """Safe, non-secret provider information for the Settings UI."""
    spec = _require_spec(provider_id)
    cfg = config or load_config()
    configured = bool(os.getenv(spec.env_var, "").strip())
    selected = spec.id == cfg.llm.provider if spec.kind == "llm" else None
    return {
        "id": spec.id,
        "name": spec.name,
        "kind": spec.kind,
        "description": spec.description,
        "env_var": spec.env_var,
        "configured": configured,
        "selected": selected,
        "capabilities": list(spec.capabilities),
        "model": cfg.llm.model_for(spec.id) if spec.kind == "llm" else None,
        "default_model": spec.default_model,
        "connection_test_supported": spec.connection_test,
    }


def all_provider_metadata(config: AppConfig | None = None) -> list[dict]:
    cfg = config or load_config()
    return [provider_metadata(spec_id, cfg) for spec_id in PROVIDERS]
