"""Minimal, comment-preserving INI updates for safe frontend settings.

Only the exact keys supplied by the caller are changed. Existing values,
comments, ordering and unknown sections are preserved. Secrets never live in
this file; environment variables remain the only credential source.
"""
from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path

_SECTION_RE = re.compile(r"^\s*\[(.+?)\]\s*$")
_KEY_RE = re.compile(r"^\s*([^=:#;]+?)\s*[=:]")


def update_ini_values(
    path: Path,
    updates: dict[tuple[str, str], str],
) -> list[str]:
    """Apply section/key updates and return a list of changed keys."""
    if not updates:
        return []

    lines = path.read_text(encoding="utf-8").splitlines() if path.is_file() else []
    headers: list[tuple[int, str]] = []
    for index, line in enumerate(lines):
        match = _SECTION_RE.match(line)
        if match:
            headers.append((index, match.group(1).strip()))

    ranges: dict[str, tuple[int, int]] = {}
    for position, (index, name) in enumerate(headers):
        end = headers[position + 1][0] if position + 1 < len(headers) else len(lines)
        ranges[name] = (index, end)

    grouped: dict[str, dict[str, str]] = {}
    for (section, key), value in updates.items():
        grouped.setdefault(section, {})[key] = str(value)

    changed: list[str] = []

    # Process bottom-up so inserted lines never invalidate earlier ranges.
    for section in sorted(grouped, key=lambda name: ranges.get(name, (10**9, 10**9))[0], reverse=True):
        options = grouped[section]
        if section not in ranges:
            continue
        start, end = ranges[section]
        missing: list[tuple[str, str]] = []
        for option, value in options.items():
            found = False
            for index in range(start + 1, end):
                line = lines[index]
                if line.lstrip().startswith(("#", ";")):
                    continue
                match = _KEY_RE.match(line)
                if match and match.group(1).strip().lower() == option.lower():
                    lines[index] = f"{option} = {value}"
                    changed.append(f"{section}.{option}")
                    found = True
                    break
            if not found:
                missing.append((option, value))

        if missing:
            insert_at = end
            while insert_at - 1 > start and not lines[insert_at - 1].strip():
                insert_at -= 1
            for option, value in missing:
                lines.insert(insert_at, f"{option} = {value}")
                insert_at += 1
                changed.append(f"{section}.{option}")

    for section, options in grouped.items():
        if section in ranges:
            continue
        if lines and lines[-1].strip():
            lines.append("")
        lines.append(f"[{section}]")
        for option, value in options.items():
            lines.append(f"{option} = {value}")
            changed.append(f"{section}.{option}")

    text = "\n".join(lines).rstrip() + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        prefix=".rubberducky-", suffix=".ini", dir=str(path.parent)
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(text)
        os.replace(temporary, path)
    except Exception:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise
    return changed
