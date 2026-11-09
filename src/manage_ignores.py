"""Interactive, approval-gated ignore-pattern suggestions.

Run from the repository root:
    uv run python src/manage_ignores.py
Only file paths (never file contents) are sent to the configured LLM.
"""
from __future__ import annotations

from dotenv import load_dotenv

from core.config import load_config
from core.ignore import IgnoreManager
from core.llm_client import LLMError, LLMErrorCode, complete_json
from core.repository import collect_candidate_paths

PATTERN_PROMPT = """You review repository PATH NAMES only and suggest safe gitignore-style patterns.
Do not suggest ignoring source code, tests, documentation, or configuration needed to build.
Prioritize generated artifacts, caches, local environment files, build outputs, and secrets.
Return only JSON: {"patterns":["pattern"]}. Never include file contents."""


def ask_ai_for_patterns(paths: list[str]) -> list[str]:
    config = load_config()
    data = complete_json(
        PATTERN_PROMPT,
        "Repository paths:\n" + "\n".join(paths),
        config=config,
        temperature=0.0,
        max_tokens=min(config.llm.max_tokens, 700),
    )
    patterns = data.get("patterns", [])
    if not isinstance(patterns, list):
        raise LLMError(
            LLMErrorCode.SCHEMA_ERROR,
            "The AI response did not contain a patterns list.",
            retryable=True,
        )
    return [item.strip() for item in patterns if isinstance(item, str) and item.strip()]


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
    except LLMError as exc:
        print(f"AI suggestions unavailable ({exc.code.value}): {exc.message}")
        suggestions = manager.suggest_patterns(paths)
        source = "local fallback"
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

    approval = input(
        f"Apply these patterns to "
        f"{'.gitignore' if destination == 'git' else '.rubberduckyignore'}? [y/N]: "
    ).strip().lower()
    if approval != "y":
        print("Cancelled. No files changed.")
        return
    applied = manager.apply_suggestions(suggestions, approved=True, destination=destination)
    print(f"Applied {len(applied)} pattern(s).")
    for pattern in applied:
        print(f"  + {pattern}")


if __name__ == "__main__":
    main()
