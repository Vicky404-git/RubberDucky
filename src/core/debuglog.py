"""Privacy-conscious diagnostic logging for RubberDucky.

Log only stage names, event labels, durations, and numeric/status metadata.
Do not pass transcripts, prompts, diffs, logs, credentials, or exception text.
"""
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from core.config import load_config

_logger = None

def get_logger():
    global _logger
    if _logger is not None:
        return _logger
    config = load_config()
    logger = logging.getLogger("rubberducky")
    logger.setLevel(getattr(logging, config.logging.level.upper(), logging.INFO))
    logger.propagate = False
    if not logger.handlers:
        path = config.project_root / "debug.log"
        handler = RotatingFileHandler(
            path, maxBytes=config.logging.max_bytes,
            backupCount=config.logging.backup_count, encoding="utf-8"
        )
        handler.setFormatter(logging.Formatter(
            "%(asctime)s | %(levelname)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        ))
        logger.addHandler(handler)
    _logger = logger
    return logger

def log_event(stage: str, event: str, *, level: str = "info", duration_ms=None, code=None):
    """Write allowlisted metadata only; caller must not pass sensitive values."""
    safe_stage = str(stage)[:40].replace("\n", " ").replace("|", "/")
    safe_event = str(event)[:100].replace("\n", " ").replace("|", "/")
    parts = [f"stage={safe_stage}", f"event={safe_event}"]
    if isinstance(duration_ms, (int, float)):
        parts.append(f"duration_ms={max(0, int(duration_ms))}")
    if isinstance(code, (int, float)):
        parts.append(f"code={int(code)}")
    method = getattr(get_logger(), level.lower(), get_logger().info)
    method(" | ".join(parts))
