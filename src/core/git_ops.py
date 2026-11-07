"""Read-only Git context helpers for RubberDucky (no repository mutations)."""
from __future__ import annotations
import subprocess
from pathlib import Path
from core.config import load_config
from core.ignore import IgnoreManager

def _run_git(args: list[str], repo_path: str | Path | None = None) -> str:
    cfg = load_config()
    cwd = Path(repo_path).resolve() if repo_path else cfg.project_root
    try:
        result = subprocess.run(
            ["git", *args], cwd=cwd, capture_output=True, text=True,
            timeout=cfg.git.timeout, check=False,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return ""
    if result.returncode != 0:
        return ""
    return result.stdout.strip()

def get_git_status(repo_path: str | Path | None = None) -> str:
    """Return concise porcelain status, excluding ignored/sensitive paths."""
    manager = IgnoreManager(repo_path or load_config().project_root)
    raw = _run_git(["status", "--short", "--branch", "--untracked-files=normal"], repo_path)
    if not raw:
        return "Git status unavailable or working tree clean."
    lines = raw.splitlines()
    safe = [lines[0]] if lines else []
    for line in lines[1:]:
        path = line[3:].strip().strip('"') if len(line) >= 4 else ""
        # Rename output can contain 'old -> new'; check both sides conservatively.
        paths = [part.strip().strip('"') for part in path.split(" -> ")]
        if path and not any(manager.is_ignored(item) for item in paths):
            safe.append(line)
    return manager.sanitize_context("\n".join(safe))

def get_staged_diff(repo_path: str | Path | None = None) -> str:
    raw = _run_git(["diff", "--cached", "--no-ext-diff", "--no-renames", "--unified=2"], repo_path)
    manager = IgnoreManager(repo_path or load_config().project_root)
    safe = manager.filter_git_diff(raw) if raw else ""
    return safe[:load_config().git.max_chars] if safe else "No staged changes."

def get_worktree_diff(repo_path: str | Path | None = None) -> str:
    raw = _run_git(["diff", "--no-ext-diff", "--no-renames", "--unified=2"], repo_path)
    manager = IgnoreManager(repo_path or load_config().project_root)
    safe = manager.filter_git_diff(raw) if raw else ""
    return safe[:load_config().git.max_chars] if safe else "No unstaged tracked changes."

def get_recent_commits(repo_path: str | Path | None = None, count: int | None = None) -> str:
    cfg = load_config()
    count = max(1, min(int(count or cfg.git.max_commits), 50))
    raw = _run_git(["log", f"-{count}", "--date=short", "--pretty=format:%h | %ad | %s"], repo_path)
    return IgnoreManager(repo_path or cfg.project_root).sanitize_context(raw) if raw else "No recent commits."

def get_merge_conflicts(repo_path: str | Path | None = None) -> str:
    raw = _run_git(["diff", "--name-only", "--diff-filter=U"], repo_path)
    if not raw:
        return "No merge conflicts detected."
    manager = IgnoreManager(repo_path or load_config().project_root)
    paths = [p for p in raw.splitlines() if not manager.is_ignored(p)]
    return "\n".join(paths) if paths else "No non-ignored merge conflicts detected."

def get_git_context(repo_path: str | Path | None = None) -> str:
    """Build compact context containing status, conflicts, staged/unstaged diff and commits."""
    cfg = load_config()
    sections = [
        "GIT STATUS:\n" + get_git_status(repo_path),
        "MERGE CONFLICTS:\n" + get_merge_conflicts(repo_path),
        "STAGED DIFF:\n" + get_staged_diff(repo_path),
        "UNSTAGED DIFF:\n" + get_worktree_diff(repo_path),
        "RECENT COMMITS:\n" + get_recent_commits(repo_path),
    ]
    result = "\n\n".join(sections)
    manager = IgnoreManager(repo_path or cfg.project_root)
    result = manager.sanitize_context(result)
    return result[:cfg.git.max_chars] + ("\n[Git context truncated]" if len(result) > cfg.git.max_chars else "")
