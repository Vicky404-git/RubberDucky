"""Shared repository candidate-path scanning for CLI and bridge callers."""
from __future__ import annotations

import os
from pathlib import Path

from core.ignore import IgnoreManager

EXCLUDED_DIRECTORIES = frozenset(
    {
        ".git",
        ".venv",
        "venv",
        "node_modules",
        "__pycache__",
        "dist",
        "build",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
    }
)
DEFAULT_CANDIDATE_LIMIT = 2000


def collect_candidate_paths(
    root: str | Path,
    manager: IgnoreManager | None = None,
    *,
    limit: int = DEFAULT_CANDIDATE_LIMIT,
) -> list[str]:
    """Return non-ignored relative file paths, pruning known generated trees."""
    base = Path(root).resolve()
    ignore_manager = manager or IgnoreManager(base)
    if limit <= 0:
        return []

    candidates: list[str] = []
    for current, directories, files in os.walk(base):
        directories[:] = sorted(
            directory
            for directory in directories
            if directory not in EXCLUDED_DIRECTORIES
        )
        for filename in sorted(files):
            relative = (Path(current) / filename).relative_to(base).as_posix()
            if ignore_manager.is_ignored(relative):
                continue
            candidates.append(relative)
            if len(candidates) >= limit:
                return candidates
    return candidates
