"""Central configuration for RubberDucky.

Configuration is read once from the project-root rubberducky.ini. Environment
variables remain the source of secrets; never put API keys in this file.
"""
from __future__ import annotations

from configparser import ConfigParser, Error as ConfigError
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "rubberducky.ini"


@dataclass(frozen=True)
class GitConfig:
    max_commits: int = 2
    max_chars: int = 4000
    timeout: int = 10


@dataclass(frozen=True)
class LLMConfig:
    provider: str = "openrouter"
    model: str = "liquid/lfm-3-1.7b:free"
    temperature: float = 0.1
    max_tokens: int = 700
    timeout: int = 25


@dataclass(frozen=True)
class TriageConfig:
    device: str = "cpu"
    lazy_load: bool = True


@dataclass(frozen=True)
class VoiceConfig:
    record_seconds: int = 5
    language: str = "hi-IN"


@dataclass(frozen=True)
class HotkeyConfig:
    key: str = "v"
    modifiers: str = "Mod4+Alt"


@dataclass(frozen=True)
class LoggingConfig:
    level: str = "INFO"
    max_bytes: int = 1048576
    backup_count: int = 3


@dataclass(frozen=True)
class AppConfig:
    project_root: Path
    config_path: Path
    git: GitConfig
    llm: LLMConfig
    triage: TriageConfig
    voice: VoiceConfig
    hotkey: HotkeyConfig
    logging: LoggingConfig


_cached_config: Optional[AppConfig] = None


def _bounded_int(parser: ConfigParser, section: str, option: str,
                 default: int, minimum: int, maximum: int) -> int:
    try:
        value = parser.getint(section, option, fallback=default)
    except (ValueError, ConfigError):
        value = default
    return max(minimum, min(value, maximum))


def _get_bool(parser: ConfigParser, section: str, option: str, default: bool) -> bool:
    try:
        return parser.getboolean(section, option, fallback=default)
    except (ValueError, ConfigError):
        return default


def _bounded_float(parser: ConfigParser, section: str, option: str,
                   default: float, minimum: float, maximum: float) -> float:
    try:
        value = parser.getfloat(section, option, fallback=default)
    except (ValueError, ConfigError):
        value = default
    return max(minimum, min(value, maximum))


def load_config(path: str | Path | None = None, *, reload: bool = False) -> AppConfig:
    """Load and validate settings. The result is cached for one process."""
    global _cached_config
    config_path = Path(path).expanduser().resolve() if path else DEFAULT_CONFIG_PATH
    if _cached_config is not None and not reload and _cached_config.config_path == config_path:
        return _cached_config

    parser = ConfigParser(interpolation=None)
    if config_path.is_file():
        try:
            parser.read(config_path, encoding="utf-8")
        except (OSError, ConfigError) as exc:
            print(f"Config warning: could not read {config_path}: {exc}")

    root = config_path.parent
    provider = parser.get("llm", "provider", fallback="openrouter").strip().lower()
    if provider != "openrouter":
        print(f"Config warning: unsupported provider '{provider}', using openrouter.")
        provider = "openrouter"

    key = parser.get("hotkey", "key", fallback="v").strip() or "v"
    modifiers = parser.get("hotkey", "modifiers", fallback="Mod4+Alt").strip() or "Mod4+Alt"

    _cached_config = AppConfig(
        project_root=root,
        config_path=config_path,
        git=GitConfig(
            max_commits=_bounded_int(parser, "git", "max_commits", 2, 1, 50),
            max_chars=_bounded_int(parser, "git", "max_chars", 4000, 500, 100000),
            timeout=_bounded_int(parser, "git", "timeout", 10, 1, 120),
        ),
        llm=LLMConfig(
            provider=provider,
            model=parser.get("llm", "model", fallback="liquid/lfm-3-1.7b:free").strip() or "liquid/lfm-3-1.7b:free",
            temperature=_bounded_float(parser, "llm", "temperature", 0.1, 0.0, 2.0),
            max_tokens=_bounded_int(parser, "llm", "max_tokens", 700, 64, 8192),
            timeout=_bounded_int(parser, "llm", "timeout", 25, 3, 180),
        ),
        triage=TriageConfig(
            device=parser.get("triage", "device", fallback="cpu").strip() or "cpu",
            lazy_load=_get_bool(parser, "triage", "lazy_load", True),
        ),
        voice=VoiceConfig(
            record_seconds=_bounded_int(parser, "voice", "record_seconds", 5, 1, 60),
            language=parser.get("voice", "language", fallback="hi-IN").strip() or "hi-IN",
        ),
        hotkey=HotkeyConfig(key=key, modifiers=modifiers),
        logging=LoggingConfig(
            level=parser.get("logging", "level", fallback="INFO").strip().upper(),
            max_bytes=_bounded_int(parser, "logging", "max_bytes", 1048576, 65536, 10485760),
            backup_count=_bounded_int(parser, "logging", "backup_count", 3, 1, 10),
        ),
    )
    return _cached_config


def reset_config_cache() -> None:
    """Clear cached settings; useful for tests and explicit config reloads."""
    global _cached_config
    _cached_config = None
