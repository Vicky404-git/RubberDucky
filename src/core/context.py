import subprocess
from typing import Optional

def get_docker_logs(container_name: str, tail: int = 50) -> Optional[str]:
    """Fetches the last N lines of logs from a specific Docker container."""
    try:
        result = subprocess.run(
            ["docker", "logs", f"--tail={tail}", container_name],
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout if result.stdout else result.stderr
    except subprocess.CalledProcessError as e:
        print(f"Failed to get Docker logs: {e.stderr}")
        return None
    except FileNotFoundError:
        print("Docker is not installed or not in PATH.")
        return None

def get_git_diff() -> Optional[str]:
    """Fetches the current uncommitted git diff."""
    try:
        result = subprocess.run(
            ["git", "diff"],
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout if result.stdout else "No uncommitted changes."
    except subprocess.CalledProcessError as e:
        print(f"Failed to get git diff: {e.stderr}")
        return None
    except FileNotFoundError:
        print("Git is not installed or not in PATH.")
        return None
