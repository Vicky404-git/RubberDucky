
import os
import re
from laya import Router

os.environ["HF_HUB_OFFLINE"] = "1"

print("⏳ Loading LAYA Triage Engine (Offline Cache)...")
router = Router(preload=True, device="cpu")


def detect_category(transcript: str) -> str | None:
    """Route obvious incidents before invoking the ML classifier."""

    text = transcript.lower()

    patterns = {
        "infrastructure": (
            r"\bdocker\b|\bcontainer\b|\bcontainers\b|\bport\b|"
            r"\bserver\b|\bdatabase\b|\bconnection\b|\bnetwork\b|"
            r"\bnginx\b|\bredis\b|\bpostgres\b|\bmysql\b|"
            r"डॉकर|कंटेनर|सर्वर|पोर्ट|डेटाबेस"
        ),
        "git_issue": (
            r"\bgit\b|\bmerge conflict\b|\bcommit\b|\bbranch\b|"
            r"\brebase\b|\bpush\b|\bpull\b|\bcheckout\b"
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
    """Classify an incident using deterministic routing and LAYA fallback."""

    print("🧠 LAYA classifying incident...")

    category = detect_category(transcript)

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

    state = {
        "transcript": transcript,
        "git_diff_snippet": git_diff[:500] if git_diff else "None",
    }

    questions = {
        "issue_category": {
            "type": "choice",
            "instructions": "Classify the user's spoken developer issue. Prioritize the transcript over git changes.",
            "criteria": {
                "syntax_error": "Syntax, indentation, or parsing errors.",
                "infrastructure": "Docker, containers, databases, ports, or server issues.",
                "logic_bug": "Incorrect output or unexpected program behavior.",
                "git_issue": "Git branches, commits, merges, or repository problems.",
            },
        },
        "requires_logs": {
            "type": "noul",
            "instructions": "Does diagnosing this issue require server or application logs?",
        },
    }

    return router.predict(state, questions)

