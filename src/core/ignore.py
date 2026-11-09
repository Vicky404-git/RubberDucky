"""Ignore rules and secret protection for AI-provided project context.

This module never changes ignore files unless apply_suggestions(..., approved=True)
is called explicitly by the application/user.
"""
from __future__ import annotations

import fnmatch
import re
import subprocess
from pathlib import Path, PurePosixPath
from typing import Iterable

try:
    from pathspec import PathSpec
except ImportError:  # A conservative fallback; install pathspec for full gitignore semantics.
    PathSpec = None

DEFAULT_SENSITIVE_PATTERNS = (
    ".env", ".env.*", "**/.env", "**/.env.*",
    "*.pem", "**/*.pem", "*.key", "**/*.key", "id_rsa", "**/id_rsa*",
    "*.p12", "*.pfx", "**/*.p12", "**/*.pfx",
    "credentials*", "**/credentials*", "secrets*", "**/secrets*",
    "**/service-account*.json", "**/*service_account*.json",
)

# Match common credential formats in diff/context text. Values are masked, not logged.
_SECRET_PATTERNS = [
    re.compile(r"(?i)(\b[\w.-]*(?:api[_-]?key|access[_-]?token|auth[_-]?token|password|passwd|client[_-]?secret|secret|database_url)[\w.-]*\s*[:=]\s*)(?:\"[^\"\r\n]*\"|'[^'\r\n]*'|[^\s,;]+)"),
    re.compile(r"\b(AKIA[0-9A-Z]{16})\b"),
    re.compile(r"\b(gh[pousr]_[A-Za-z0-9]{20,})\b"),
    re.compile(r"\b(sk-[A-Za-z0-9_-]{20,})\b"),
    re.compile(r"\b(xox[baprs]-[A-Za-z0-9-]{10,})\b"),
]


def _read_patterns(path: Path) -> list[str]:
    if not path.is_file():
        return []
    try:
        return [line.strip() for line in path.read_text(encoding="utf-8").splitlines()
                if line.strip() and not line.lstrip().startswith("#")]
    except OSError:
        return []


class IgnoreManager:
    def __init__(self, repo_path: str | Path | None = None):
        self.repo_path = Path(repo_path).resolve() if repo_path else Path.cwd().resolve()
        self.gitignore_path = self.repo_path / ".gitignore"
        self.rubberduckyignore_path = self.repo_path / ".rubberduckyignore"
        self.reload()

    def reload(self) -> None:
        self.git_patterns = _read_patterns(self.gitignore_path)
        self.rubber_user_patterns = _read_patterns(self.rubberduckyignore_path)
        self.rubber_patterns = list(DEFAULT_SENSITIVE_PATTERNS) + self.rubber_user_patterns
        self._sensitive_spec = self._compile(list(DEFAULT_SENSITIVE_PATTERNS))
        self._git_spec = self._compile(self.git_patterns)
        self._rubber_spec = self._compile(self.rubber_user_patterns)

    @staticmethod
    def _compile(patterns: list[str]):
        if PathSpec is None:
            return None
        return PathSpec.from_lines("gitignore", patterns)

    @staticmethod
    def _fallback_match(path: str, patterns: list[str]) -> bool:
        normalized = path.replace("\\", "/")
        if normalized.startswith("./"):
            normalized = normalized[2:]
        parts = normalized.split("/")
        for raw in patterns:
            pattern = raw.strip()
            if not pattern or pattern.startswith("!"):
                continue
            pattern = pattern.lstrip("/")
            if pattern.endswith("/"):
                directory = pattern.rstrip("/")
                if normalized == directory or normalized.startswith(directory + "/"):
                    return True
            if fnmatch.fnmatch(normalized, pattern) or any(fnmatch.fnmatch(p, pattern) for p in parts):
                return True
        return False

    def _matches(self, path: str, patterns: list[str], spec) -> bool:
        normalized = PurePosixPath(path.replace("\\", "/")).as_posix()
        if spec is not None:
            return bool(spec.match_file(normalized))
        return self._fallback_match(normalized, patterns)

    def is_ignored(self, relative_path: str) -> bool:
        path = relative_path.replace("\\", "/")
        if path.startswith("./"):
            path = path[2:]
        # RubberDucky exclusions and built-in secret rules are always enforced.
        if self._matches(path, list(DEFAULT_SENSITIVE_PATTERNS), self._sensitive_spec):
            return True
        if self._matches(path, self.rubber_user_patterns, self._rubber_spec):
            return True
        # Apply .gitignore rules even to tracked files in historical diffs.
        return self._matches(path, self.git_patterns, self._git_spec)

    @staticmethod
    def _diff_paths(header: str) -> list[str]:
        match = re.match(r"^diff --git a/(.*?) b/(.*?)\s*$", header)
        if not match:
            return []
        # Git quotes unusual paths; standard repository paths are unquoted.
        return [match.group(1).strip('"'), match.group(2).strip('"')]

    def filter_git_diff(self, diff: str) -> str:
        """Drop ignored file sections, then redact secrets in remaining patch text."""
        if not diff:
            return ""
        lines = diff.splitlines(keepends=True)
        sections: list[list[str]] = []
        preamble: list[str] = []
        current: list[str] | None = None
        for line in lines:
            if line.startswith("diff --git "):
                if current is not None:
                    sections.append(current)
                current = [line]
            elif current is None:
                preamble.append(line)
            else:
                current.append(line)
        if current is not None:
            sections.append(current)

        kept: list[str] = list(preamble)
        for section in sections:
            paths = self._diff_paths(section[0])
            # Fail closed: if a patch header cannot be parsed, do not send its contents.
            if not paths or any(self.is_ignored(path) for path in paths):
                continue
            kept.extend(section)
        return self.redact_secrets("".join(kept)).strip()

    @staticmethod
    def redact_secrets(text: str) -> str:
        if not text:
            return text
        # Hide PEM/private-key blocks as a whole.
        text = re.sub(
            r"-----BEGIN [^-]*PRIVATE KEY-----.*?-----END [^-]*PRIVATE KEY-----",
            "[REDACTED PRIVATE KEY BLOCK]", text, flags=re.DOTALL,
        )
        for index, pattern in enumerate(_SECRET_PATTERNS):
            if index == 0:
                text = pattern.sub(lambda m: m.group(1) + "[REDACTED]", text)
            else:
                text = pattern.sub("[REDACTED]", text)
        return text

    def sanitize_context(self, text: str) -> str:
        """Redact likely credentials in logs/prompts even when no file path exists."""
        return self.redact_secrets(text or "")

    def sensitive_findings(self, paths: Iterable[str], limit: int = 100) -> list[str]:
        """Return paths matching built-in secret patterns, deduplicated."""
        findings = [
            path
            for path in paths
            if self._matches(
                path.replace("\\", "/"),
                list(DEFAULT_SENSITIVE_PATTERNS),
                self._sensitive_spec,
            )
        ]
        return sorted(dict.fromkeys(findings))[:limit]

    def suggest_patterns(self, paths: Iterable[str]) -> list[str]:
        """Generate deterministic suggestions; an LLM may add suggestions separately."""
        suggestions: set[str] = set()
        for raw in paths:
            path = raw.replace("\\", "/").strip().lstrip("./")
            lower = path.lower()
            name = PurePosixPath(path).name
            if name in {".env", ".env.local", "id_rsa", "credentials.json"}:
                suggestions.add(path)
            elif lower.endswith((".pem", ".p12", ".pfx", ".key")):
                suggestions.add(path)
            elif "/__pycache__/" in f"/{path}/" or name.endswith(".pyc"):
                suggestions.add("__pycache__/" if "__pycache__" in path else "*.py[cod]")
            elif any(part in {"node_modules", ".venv", "venv", "dist", "build"} for part in path.split("/")):
                part = next(part for part in path.split("/") if part in {"node_modules", ".venv", "venv", "dist", "build"})
                suggestions.add(f"{part}/")
        return sorted(suggestions)

    def preview_suggestions(self, patterns: Iterable[str]) -> str:
        existing = set(self.git_patterns) | set(self.rubber_user_patterns) | set(DEFAULT_SENSITIVE_PATTERNS)
        clean = [p.strip() for p in patterns if p and p.strip() and not p.strip().startswith("#")]
        if not clean:
            return "No ignore suggestions."
        return "\n".join(("[already present] " if p in existing else "[proposed] ") + p for p in clean)

    def apply_suggestions(self, patterns: Iterable[str], *, approved: bool = False,
                          destination: str = "rubberducky") -> list[str]:
        """Append suggestions only after explicit approval. Returns applied patterns."""
        if not approved:
            raise PermissionError("Ignore suggestions require explicit user approval.")
        if destination not in {"rubberducky", "git"}:
            raise ValueError("destination must be 'rubberducky' or 'git'.")
        target = self.rubberduckyignore_path if destination == "rubberducky" else self.gitignore_path
        existing = set(_read_patterns(target))
        additions = []
        for raw in patterns:
            pattern = str(raw).strip()
            if not pattern or pattern.startswith("#") or pattern in existing:
                continue
            if "\n" in pattern or "\r" in pattern:
                continue
            additions.append(pattern)
            existing.add(pattern)
        if additions:
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("a", encoding="utf-8") as handle:
                if target.exists() and target.stat().st_size:
                    handle.write("\n")
                handle.write("# Added by RubberDucky with user approval\n")
                handle.write("\n".join(additions) + "\n")
            self.reload()
        return additions


def create_ignore_manager(repo_path: str | Path | None = None) -> IgnoreManager:
    return IgnoreManager(repo_path)
