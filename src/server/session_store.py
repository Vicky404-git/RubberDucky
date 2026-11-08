"""Small persistent store for frontend debug sessions.

Session records contain only user-facing pipeline output (transcript,
classification, diagnosis, spoken response). Raw prompts, API keys and
unfiltered source context are never written here.
"""
from __future__ import annotations

import json
import os
import tempfile
import threading
from pathlib import Path

from server.models import SessionRecord

MAX_SESSIONS = 100


def state_dir() -> Path:
    override = os.getenv("RUBBERDUCKY_STATE_DIR")
    if override:
        base = Path(override).expanduser()
    else:
        base = Path(os.getenv("XDG_STATE_HOME", Path.home() / ".local/state")) / "rubberducky"
    base.mkdir(parents=True, exist_ok=True)
    try:
        base.chmod(0o700)
    except OSError:
        pass
    return base


class SessionStore:
    def __init__(self, directory: Path | None = None) -> None:
        self.directory = directory or state_dir()
        self.audio_dir = self.directory / "audio"
        self.audio_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.directory / "sessions.json"
        self._lock = threading.RLock()
        self._sessions: dict[str, SessionRecord] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.is_file():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        if not isinstance(raw, list):
            return
        for item in raw:
            try:
                record = SessionRecord.model_validate(item)
            except Exception:
                continue
            self._sessions[record.id] = record

    def _save_locked(self) -> None:
        records = sorted(self._sessions.values(), key=lambda item: item.started_at, reverse=True)[
            :MAX_SESSIONS
        ]
        payload = [record.model_dump() for record in records]
        descriptor, temporary = tempfile.mkstemp(
            prefix=".sessions-", suffix=".json", dir=str(self.directory)
        )
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2)
            try:
                os.chmod(temporary, 0o600)
            except OSError:
                pass
            os.replace(temporary, self.path)
        except Exception:
            try:
                os.unlink(temporary)
            except OSError:
                pass
            raise

    def list(self, limit: int = 50) -> list[SessionRecord]:
        with self._lock:
            records = sorted(
                self._sessions.values(), key=lambda item: item.started_at, reverse=True
            )
            return records[: max(1, min(limit, MAX_SESSIONS))]

    def get(self, session_id: str) -> SessionRecord | None:
        with self._lock:
            return self._sessions.get(session_id)

    def latest(self) -> SessionRecord | None:
        with self._lock:
            if not self._sessions:
                return None
            return max(self._sessions.values(), key=lambda item: item.started_at)

    def upsert(self, record: SessionRecord) -> SessionRecord:
        with self._lock:
            self._sessions[record.id] = record
            # Also evict the oldest records when the store grows too large.
            if len(self._sessions) > MAX_SESSIONS:
                for stale in sorted(
                    self._sessions.values(), key=lambda item: item.started_at
                )[: len(self._sessions) - MAX_SESSIONS]:
                    self._sessions.pop(stale.id, None)
            self._save_locked()
            return record

    def audio_path(self, session_id: str) -> Path:
        return self.audio_dir / f"{session_id}.wav"

    def clear(self) -> None:
        with self._lock:
            self._sessions.clear()
            self._save_locked()


session_store = SessionStore()
