
import subprocess
from pathlib import Path
from typing import Optional


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
            [
                "docker",
                "logs",
                f"--tail={tail}",
                container_name.strip(),
            ],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )

        if result.returncode != 0:
            error = result.stderr.strip() or "Unknown Docker error."
            print(f"Docker Error: {error}")
            return None

        output = result.stdout or result.stderr

        if not output.strip():
            print("Docker: No logs returned.")
            return None

        return output

    except subprocess.TimeoutExpired:
        print("Docker Error: Log retrieval timed out.")
        return None

    except FileNotFoundError:
        print("Docker Error: Docker is not installed or not in PATH.")
        return None

    except OSError as exc:
        print(f"Docker System Error: {exc}")
        return None


def get_git_diff(
    repo_path: Optional[str] = None,
    timeout: int = 10,
    max_chars: int = 4000,
    max_commits=2,
) -> str:
    """Return patches from the latest 5 commits, bounded in size."""

    cwd = Path(repo_path).resolve() if repo_path else None

    try:
        result = subprocess.run(
            [
                "git",
                "log",
                f"-{max_commits}",
                "--no-ext-diff",
                "--no-renames",
                "--format=\nCOMMIT %h | %s | %cs",
                "--patch",
                "--unified=2",
                "--",
                ".",
                ":(exclude)ducky-daemon",
            ],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )

        if result.returncode != 0:
            error = result.stderr.strip() or "Git history unavailable."
            print(f"Git Error: {error}")
            return "Git commit history unavailable."

        diff = result.stdout.strip()

        if not diff:
            return "No commit history available."

        if len(diff) > max_chars:
            diff = diff[:max_chars] + "\n\n[Git history truncated]"

        return diff

    except subprocess.TimeoutExpired:
        print("Git Error: History retrieval timed out.")
        return "Git context unavailable due to timeout."

    except FileNotFoundError:
        print("Git Error: Git is not installed or not in PATH.")
        return "Git is unavailable."

    except OSError as exc:
        print(f"Git System Error: {exc}")
        return "Git context unavailable."
