import subprocess
from pathlib import Path
from typing import Optional

from core.config import load_config
from core.ignore import IgnoreManager


def get_docker_logs(
    container_name: str,
    tail: int = 50,
    timeout: int = 10,
) -> Optional[str]:
    """Fetch recent logs from a Docker container."""
    if not container_name or not container_name.strip():
        print("Docker Error: Container name is empty.")
        return None
    if tail <= 0:
        print("Docker Error: Tail must be positive.")
        return None
    try:
        result = subprocess.run(
            ["docker", "logs", f"--tail={tail}", container_name.strip()],
            capture_output=True, text=True, timeout=timeout, check=False,
        )
        if result.returncode != 0:
            print(f"Docker Error: {result.stderr.strip() or 'Unknown Docker error.'}")
            return None
        output = result.stdout or result.stderr
        if not output.strip():
            print("Docker: No logs returned.")
            return None
        return IgnoreManager().sanitize_context(output)
    except subprocess.TimeoutExpired:
        print("Docker Error: Log retrieval timed out.")
    except FileNotFoundError:
        print("Docker Error: Docker is not installed or not in PATH.")
    except OSError as exc:
        print(f"Docker System Error: {type(exc).__name__}")
    return None


def get_git_diff(
    repo_path: Optional[str] = None,
    timeout: Optional[int] = None,
    max_chars: Optional[int] = None,
    max_commits: Optional[int] = None,
) -> str:
    """Return recent commit patches after ignore filtering and secret redaction."""
    config = load_config()
    timeout = timeout if timeout is not None else config.git.timeout
    max_chars = max_chars if max_chars is not None else config.git.max_chars
    max_commits = max_commits if max_commits is not None else config.git.max_commits
    max_commits = max(1, min(int(max_commits), 50))
    max_chars = max(500, min(int(max_chars), 100000))
    cwd = Path(repo_path).resolve() if repo_path else config.project_root
    ignore_manager = IgnoreManager(cwd)

    try:
        result = subprocess.run(
            [
                "git", "log", f"-{max_commits}", "--no-ext-diff", "--no-renames",
                "--format=\nCOMMIT %h | %s | %cs", "--patch", "--unified=2",
                "--", ".", ":(exclude)ducky-daemon",
            ],
            cwd=cwd, capture_output=True, text=True,
            timeout=timeout, check=False,
        )
        if result.returncode != 0:
            print(f"Git Error: {result.stderr.strip() or 'History unavailable.'}")
            return "Git commit history unavailable."
        raw_diff = result.stdout.strip()
        if not raw_diff:
            return "No commit history available."
        filtered = ignore_manager.filter_git_diff(raw_diff)
        if not filtered:
            return "No non-ignored Git changes available for AI context."
        if len(filtered) > max_chars:
            filtered = filtered[:max_chars] + "\n\n[Git history truncated]"
        return filtered
    except subprocess.TimeoutExpired:
        print("Git Error: History retrieval timed out.")
        return "Git context unavailable due to timeout."
    except FileNotFoundError:
        print("Git Error: Git is not installed or not in PATH.")
        return "Git is unavailable."
    except OSError as exc:
        print(f"Git System Error: {type(exc).__name__}")
        return "Git context unavailable."
