"""Interactive, approval-gated ignore-pattern suggestions.

Run from the repository root:
    uv run python src/manage_ignores.py
Only file paths (never file contents) are sent to the configured LLM.
"""
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

from core.config import load_config
from core.ignore import IgnoreManager


def collect_candidate_paths(root: Path, manager: IgnoreManager, limit: int = 1500) -> list[str]:
    candidates: list[str] = []
    skip_dirs = {".git", ".venv", "venv", "node_modules", "__pycache__"}
    for current, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in skip_dirs]
        for filename in files:
            full = Path(current) / filename
            relative = full.relative_to(root).as_posix()
            if not manager.is_ignored(relative):
                candidates.append(relative)
                if len(candidates) >= limit:
                    return candidates
    return candidates


def ask_ai_for_patterns(paths: list[str]) -> list[str]:
    config = load_config()
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY is missing.")
    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
        timeout=config.llm.timeout,
        max_retries=0,
    )
    response = client.chat.completions.create(
        model=config.llm.model,
        messages=[
            {
                "role": "system",
                "content": (
                    "You review repository PATH NAMES only and suggest safe gitignore-style patterns. "
                    "Do not suggest ignoring source code, tests, documentation, or configuration needed to build. "
                    "Prioritize generated artifacts, caches, local environment files, build outputs, and secrets. "
                    "Return only JSON: {\"patterns\":[\"pattern\"]}. Never include file contents."
                ),
            },
            {"role": "user", "content": "Repository paths:\n" + "\n".join(paths)},
        ],
        response_format={"type": "json_object"},
        temperature=0.0,
        max_tokens=min(config.llm.max_tokens, 700),
    )
    content = response.choices[0].message.content if response.choices else ""
    data = json.loads(content or "{}")
    patterns = data.get("patterns", [])
    if not isinstance(patterns, list):
        raise ValueError("Model response did not contain a patterns list.")
    return [str(item).strip() for item in patterns if isinstance(item, str) and item.strip()]


def main() -> None:
    load_dotenv()
    config = load_config()
    manager = IgnoreManager(config.project_root)
    paths = collect_candidate_paths(config.project_root, manager)
    if not paths:
        print("No candidate paths found.")
        return

    try:
        suggestions = ask_ai_for_patterns(paths)
        source = "AI"
    except Exception as exc:
        print(f"AI suggestions unavailable ({type(exc).__name__}); using local heuristics.")
        suggestions = manager.suggest_patterns(paths)
        source = "local fallback"

    suggestions = list(dict.fromkeys(suggestions))
    if not suggestions:
        print("No ignore suggestions.")
        return

    print(f"\nSuggested patterns ({source}):")
    print(manager.preview_suggestions(suggestions))
    print("\nChoose destination:")
    print("1. .rubberduckyignore (exclude from AI context only)")
    print("2. .gitignore (exclude from Git tracking where applicable)")
    choice = input("Destination [1/2, default 1]: ").strip() or "1"
    destination = "git" if choice == "2" else "rubberducky"
    if choice not in {"1", "2"}:
        print("Invalid choice. Nothing changed.")
        return

    approval = input(f"Apply these patterns to {'.gitignore' if destination == 'git' else '.rubberduckyignore'}? [y/N]: ").strip().lower()
    if approval != "y":
        print("Cancelled. No files changed.")
        return
    applied = manager.apply_suggestions(suggestions, approved=True, destination=destination)
    print(f"Applied {len(applied)} pattern(s).")
    for pattern in applied:
        print(f"  + {pattern}")


if __name__ == "__main__":
    main()
