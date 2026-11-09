import subprocess
from typing import Optional

from core.git_ops import get_git_context
from core.ignore import IgnoreManager


def get_docker_logs(container_name: str, tail: int = 50, timeout: int = 10) -> Optional[str]:
    """Fetch recent container logs and sanitize them before returning."""
    if not container_name or not container_name.strip() or tail <= 0:
        return None
    try:
        result = subprocess.run(
            ["docker", "logs", f"--tail={tail}", container_name.strip()],
            capture_output=True, text=True, timeout=timeout, check=False,
        )
        if result.returncode != 0:
            print("Docker Error: log retrieval failed.")
            return None
        output = result.stdout or result.stderr
        return IgnoreManager().sanitize_context(output) if output.strip() else None
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as exc:
        print(f"Docker Error: {type(exc).__name__}")
        return None


def get_git_diff(
    repo_path: Optional[str] = None,
    timeout=None,
    max_chars=None,
    max_commits=None,
) -> str:
    """Backward-compatible name for the shared Git context formatter."""
    return get_git_context(repo_path)
