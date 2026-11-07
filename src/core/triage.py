import os
import re
import time

# Set this BEFORE importing LAYA / Hugging Face components.
os.environ["HF_HUB_OFFLINE"] = "1"

_router = None


def get_router():
    """Load LAYA once, only when keyword routing cannot classify the issue."""
    global _router

    if _router is None:
        from laya import Router

        print("⏳ Loading LAYA (first use)...")
        start = time.perf_counter()
        _router = Router(preload=True, device="cpu")
        print(f"[TIMING] LAYA preload: {time.perf_counter() - start:.2f}s")

    return _router


def detect_category(transcript: str) -> str | None:
    text = transcript.lower()

    patterns = {
        "infrastructure": (
            r"\bdocker\b|\bcontainer\b|\bcontainers\b|\bport\b|"
            r"\bserver\b|\bdatabase\b|\bconnection\b|\bnetwork\b|"
            r"\bnginx\b|\bredis\b|\bpostgres\b|\bmysql\b|"
            r"डॉकर|कंटेनर|सर्वर|पोर्ट|डेटाबेस|नेटवर्क"
        ),
        "git_issue": (
            r"\bgit\b|\bmerge conflict\b|\bcommit\b|\bbranch\b|"
            r"\brebase\b|\bpush\b|\bpull\b|\bcheckout\b|"
            r"\bdiff\b|\bdifferences\b|"
            r"गिट|गिट डिफ|गेट डिफ|डिफरेंस|डिफरेंसेस|"
            r"कमिट|ब्रांच|मर्ज|पुश|पुल|चेकआउट"
        ),
        "syntax_error": (
            r"\bsyntax error\b|\bsyntax\b|\bindentation error\b|"
            r"\bsyntaxerror\b|\bmissing parenthesis\b"
        ),
        "logic_bug": (
            r"\bwrong output\b|\bincorrect output\b|\bwrong result\b|"
            r"\blogic bug\b|\bunexpected behavior\b|\bnot working\b"
        ),
    }

    for category, pattern in patterns.items():
        if re.search(pattern, text):
            return category

    return None


def triage_incident(transcript: str, git_diff: str = "") -> dict:
    print("🧠 Running incident triage...")

    category = detect_category(transcript)

    # Fast path: no LAYA import, loading, or inference.
    if category:
        print(f"⚡ Direct routing: {category}")
        return {
            "answers": {
                "issue_category": {
                    "choice": category,
                    "probabilities": {},
                    "source": "keyword_router",
                },
                "requires_logs": {
                    "noul": 1.0 if category == "infrastructure" else 0.0,
                    "source": "keyword_router",
                },
            }
        }

    # Slow path: only ambiguous/unmatched speech reaches LAYA.
    state = {
        "transcript": transcript,
        "git_diff_snippet": git_diff[:500] if git_diff else "None",
    }

    questions = {
        "issue_category": {
            "type": "choice",
            "instructions": (
                "Classify the spoken developer issue. "
                "Prioritize the transcript over Git changes."
            ),
            "criteria": {
                "syntax_error": "Syntax, indentation, or parsing errors.",
                "infrastructure": "Docker, containers, databases, ports, or servers.",
                "logic_bug": "Incorrect output or unexpected behavior.",
                "git_issue": "Git branches, commits, merges, or repository problems.",
            },
        },
        "requires_logs": {
            "type": "noul",
            "instructions": "Are server or application logs needed to diagnose this issue?",
        },
    }

    router = get_router()

    start = time.perf_counter()
    result = router.predict(state, questions)
    print(f"[TIMING] LAYA inference: {time.perf_counter() - start:.2f}s")

    return result
