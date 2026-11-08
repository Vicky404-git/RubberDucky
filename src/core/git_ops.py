"""Read-only Git context helpers for RubberDucky (no repository mutations).

This module is the single place that executes Git subprocesses. Callers receive
either a structured :class:`GitContext` or a formatted, redacted text snapshot.
"""
from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from core.config import AppConfig, load_config
from core.ignore import IgnoreManager

NO_STATUS = "Git status unavailable or working tree clean."
NO_CONFLICTS = "No merge conflicts detected."
NO_IGNORED_CONFLICTS = "No non-ignored merge conflicts detected."
NO_STAGED = "No staged changes."
NO_UNSTAGED = "No unstaged tracked changes."
NO_COMMITS = "No recent commits."


@dataclass(frozen=True)
class GitCommit:
    hash: str
    date: str
    subject: str

    def to_dict(self) -> dict[str, str]:
        return {"hash": self.hash, "date": self.date, "subject": self.subject}


@dataclass(frozen=True)
class GitContext:
    branch: str
    clean: bool
    status_lines: list[str]
    conflicts: list[str]
    has_conflicts: bool
    staged_diff: str
    unstaged_diff: str
    commits: list[GitCommit]
    ignored_paths: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "branch": self.branch,
            "clean": self.clean,
            "status_lines": list(self.status_lines),
            "conflicts": list(self.conflicts),
            "has_conflicts": self.has_conflicts,
            "staged_diff": self.staged_diff,
            "unstaged_diff": self.unstaged_diff,
            "commits": [commit.to_dict() for commit in self.commits],
            "ignored_paths": list(self.ignored_paths),
        }


def _run_git(
    args: list[str],
    repo_path: str | Path | None = None,
    *,
    config: AppConfig | None = None,
) -> str:
    cfg = config or load_config()
    cwd = Path(repo_path).resolve() if repo_path else cfg.project_root
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=cfg.git.timeout,
            check=False,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return ""
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def current_branch(
    repo_path: str | Path | None = None,
    *,
    config: AppConfig | None = None,
) -> str:
    branch = _run_git(["rev-parse", "--abbrev-ref", "HEAD"], repo_path, config=config)
    return branch or "unknown"


def _status_path(line: str) -> str:
    if len(line) < 4:
        return ""
    return line[3:].strip().strip('"')


def _parse_status(
    raw: str,
    manager: IgnoreManager,
) -> tuple[list[str], list[str]]:
    """Split one ``git status`` call into safe status lines and ignored paths."""
    if not raw:
        return [], []
    status_lines: list[str] = []
    ignored: list[str] = []
    for line in raw.splitlines():
        if line.startswith("## "):
            status_lines.append(line)
            continue
        if line.startswith("!! "):
            ignored.append(manager.sanitize_context(line[3:].strip().strip('"')))
            continue
        path = _status_path(line)
        # Rename output can contain 'old -> new'; check both sides conservatively.
        paths = [part.strip().strip('"') for part in path.split(" -> ")]
        if path and not any(manager.is_ignored(item) for item in paths):
            status_lines.append(manager.sanitize_context(line))
    return status_lines, sorted(dict.fromkeys(path for path in ignored if path))[:300]


def _filter_diff(
    raw: str,
    manager: IgnoreManager,
    *,
    empty_text: str,
    max_chars: int,
) -> str:
    safe = manager.filter_git_diff(raw) if raw else ""
    return safe[:max_chars] if safe else empty_text


def get_git_status(
    repo_path: str | Path | None = None,
    *,
    config: AppConfig | None = None,
) -> str:
    """Return concise porcelain status, excluding ignored/sensitive paths."""
    cfg = config or load_config()
    manager = IgnoreManager(repo_path or cfg.project_root)
    raw = _run_git(
        ["status", "--short", "--branch", "--untracked-files=normal"],
        repo_path,
        config=cfg,
    )
    if not raw:
        return NO_STATUS
    status_lines, _ = _parse_status(raw, manager)
    return "\n".join(status_lines) if status_lines else NO_STATUS


def get_staged_diff(
    repo_path: str | Path | None = None,
    *,
    config: AppConfig | None = None,
) -> str:
    cfg = config or load_config()
    manager = IgnoreManager(repo_path or cfg.project_root)
    raw = _run_git(
        ["diff", "--cached", "--no-ext-diff", "--no-renames", "--unified=2"],
        repo_path,
        config=cfg,
    )
    return _filter_diff(
        raw,
        manager,
        empty_text=NO_STAGED,
        max_chars=cfg.git.max_chars,
    )


def get_worktree_diff(
    repo_path: str | Path | None = None,
    *,
    config: AppConfig | None = None,
) -> str:
    cfg = config or load_config()
    manager = IgnoreManager(repo_path or cfg.project_root)
    raw = _run_git(
        ["diff", "--no-ext-diff", "--no-renames", "--unified=2"],
        repo_path,
        config=cfg,
    )
    return _filter_diff(
        raw,
        manager,
        empty_text=NO_UNSTAGED,
        max_chars=cfg.git.max_chars,
    )


def get_recent_commits(
    repo_path: str | Path | None = None,
    count: int | None = None,
    *,
    config: AppConfig | None = None,
) -> str:
    cfg = config or load_config()
    limit = max(1, min(int(count or cfg.git.max_commits), 50))
    raw = _run_git(
        ["log", f"-{limit}", "--date=short", "--pretty=format:%h | %ad | %s"],
        repo_path,
        config=cfg,
    )
    return IgnoreManager(repo_path or cfg.project_root).sanitize_context(raw) if raw else NO_COMMITS


def get_merge_conflicts(
    repo_path: str | Path | None = None,
    *,
    config: AppConfig | None = None,
) -> str:
    cfg = config or load_config()
    raw = _run_git(
        ["diff", "--name-only", "--diff-filter=U"],
        repo_path,
        config=cfg,
    )
    if not raw:
        return NO_CONFLICTS
    manager = IgnoreManager(repo_path or cfg.project_root)
    paths = [path for path in raw.splitlines() if not manager.is_ignored(path)]
    return "\n".join(paths) if paths else NO_IGNORED_CONFLICTS


def _parse_commits(raw: str) -> list[GitCommit]:
    if not raw or raw.startswith(NO_COMMITS):
        return []
    commits: list[GitCommit] = []
    for line in raw.splitlines():
        parts = [part.strip() for part in line.split("|", 2)]
        if len(parts) == 3:
            commits.append(GitCommit(hash=parts[0], date=parts[1], subject=parts[2]))
    return commits


def _parse_conflicts(raw: str) -> list[str]:
    if raw in {NO_CONFLICTS, NO_IGNORED_CONFLICTS}:
        return []
    return [line for line in raw.splitlines() if line.strip()]


def _git_context_unavailable_reason(root: Path) -> str:
    """Return a useful reason when Git context cannot be collected."""
    if shutil.which("git") is None:
        return "Git is unavailable (git executable not found)."
    if not root.exists() or not root.is_dir():
        return "Git is unavailable (repository path does not exist)."
    return "Git context unavailable (not a repository or Git status failed)."


def collect_git_context(repo_path: str | Path | None = None) -> GitContext:
    """Collect Git context once, using one subprocess per Git operation."""
    cfg = load_config()
    root = Path(repo_path).resolve() if repo_path else cfg.project_root
    manager = IgnoreManager(root)

    status_raw = _run_git(
        ["status", "--short", "--branch", "--untracked-files=normal", "--ignored"],
        root,
        config=cfg,
    )
    if status_raw:
        status_lines, ignored_paths = _parse_status(status_raw, manager)
        changed = any(not line.startswith("## ") for line in status_lines)
    else:
        # `git status` always emits a branch header, even for a clean tree. An
        # empty result therefore indicates failure, not a clean repository.
        status_lines = [_git_context_unavailable_reason(root)]
        ignored_paths = []
        changed = True

    conflicts = _parse_conflicts(get_merge_conflicts(root, config=cfg))
    commits = _parse_commits(get_recent_commits(root, config=cfg))

    return GitContext(
        branch=current_branch(root, config=cfg),
        clean=not changed,
        status_lines=status_lines,
        conflicts=conflicts,
        has_conflicts=bool(conflicts),
        staged_diff=get_staged_diff(root, config=cfg),
        unstaged_diff=get_worktree_diff(root, config=cfg),
        commits=commits,
        ignored_paths=ignored_paths,
    )


def format_git_context(
    context: GitContext,
    *,
    max_chars: int | None = None,
    include_ignored: bool = False,
    repo_path: str | Path | None = None,
) -> str:
    """Format structured context for LLM consumption with existing size limits."""
    cfg = load_config()
    limit = cfg.git.max_chars if max_chars is None else max_chars
    status_text = "\n".join(context.status_lines) if context.status_lines else NO_STATUS
    conflicts_text = "\n".join(context.conflicts) if context.conflicts else NO_CONFLICTS
    commits_text = (
        "\n".join(
            f"{commit.hash} | {commit.date} | {commit.subject}"
            for commit in context.commits
        )
        or NO_COMMITS
    )
    sections = [
        "GIT STATUS:\n" + status_text,
        "MERGE CONFLICTS:\n" + conflicts_text,
        "STAGED DIFF:\n" + context.staged_diff,
        "UNSTAGED DIFF:\n" + context.unstaged_diff,
        "RECENT COMMITS:\n" + commits_text,
    ]
    if include_ignored:
        sections.append(
            "IGNORED PATHS:\n" + ("\n".join(context.ignored_paths) or "None.")
        )
    result = "\n\n".join(sections)
    result = IgnoreManager(repo_path or cfg.project_root).sanitize_context(result)
    return result[:limit] + (
        "\n[Git context truncated]" if len(result) > limit else ""
    )


def git_context_summary(context: GitContext) -> str:
    """Compact, human-readable summary used in a session record."""
    changed = sum(1 for line in context.status_lines if not line.startswith("## "))
    commits = len(context.commits)
    conflicts = len(context.conflicts)
    return (
        f"{context.branch} · "
        f"{changed} changed path{'s' if changed != 1 else ''} · "
        f"{commits} recent commit{'s' if commits != 1 else ''}"
        + (f" · {conflicts} conflict{'s' if conflicts != 1 else ''}" if conflicts else "")
    )


def get_git_context(repo_path: str | Path | None = None) -> str:
    """Backward-compatible text snapshot built from one structured collection."""
    context = collect_git_context(repo_path)
    return format_git_context(context, repo_path=repo_path)
