"""Read-only Git projection for the frontend.

All repository access goes through core.git_ops; this module only reshapes the
shared structured context into typed JSON. No Git mutation is possible.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from core.git_ops import (
    GitContext,
    collect_git_context,
    current_branch,
    git_context_summary,
)

__all__ = ["build_git_context", "current_branch", "session_git_summary"]


def build_git_context(repo_path: Path | str | None = None) -> dict[str, Any]:
    """Return the frontend API shape from a single Git context collection."""
    return collect_git_context(repo_path).to_dict()


def session_git_summary(context: GitContext | dict[str, Any]) -> str:
    """Compact, human-readable summary used in a session record."""
    if isinstance(context, GitContext):
        return git_context_summary(context)
    status_lines = context.get("status_lines", [])
    changes = max(0, len(status_lines) - 1)
    commits = len(context.get("commits", []))
    conflicts = len(context.get("conflicts", []))
    return (
        f"{context.get('branch', 'unknown')} · "
        f"{changes} changed path{'s' if changes != 1 else ''} · "
        f"{commits} recent commit{'s' if commits != 1 else ''}"
        + (f" · {conflicts} conflict{'s' if conflicts != 1 else ''}" if conflicts else "")
    )
