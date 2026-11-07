import os
import re
import time

from core.config import load_config

# Set this BEFORE importing LAYA / Hugging Face components.
os.environ["HF_HUB_OFFLINE"] = "1"
_router = None
_router_device = None


def get_router(device: str | None = None):
    """Load LAYA once, using the configured inference device."""
    global _router, _router_device
    config = load_config()
    selected_device = device or config.triage.device
    if _router is None or _router_device != selected_device:
        from laya import Router
        print(f"⏳ Loading LAYA on {selected_device} (first use)...")
        start = time.perf_counter()
        _router = Router(preload=True, device=selected_device)
        _router_device = selected_device
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
            r"\bgit\b|\bgit status\b|\bstatus\b|\bworking tree\b|"
            r"\bmerge conflict\b|\bcommit\b|\bbranch\b|\brebase\b|"
            r"\bpush\b|\bpull\b|\bcheckout\b|\bdiff\b|\bdifferences\b|"
            r"गिट|गेट|स्टेटस|स्थिति|गिट डिफ|गेट डिफ|डिफरेंस|डिफरेंसेस|"
            r"कमिट|ब्रांच|मर्ज|पुश|पुल|चेकआउट|स्टेज्ड|अनकमिटेड"
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
    config = load_config()
    category = detect_category(transcript)

    # Optional eager preload; keyword matches still bypass inference.
    router = None
    if not config.triage.lazy_load:
        router = get_router(config.triage.device)

    if category:
        print(f"⚡ Direct routing: {category}")
        return {
            "answers": {
                "issue_category": {"choice": category, "probabilities": {}, "source": "keyword_router"},
                "requires_logs": {"noul": 1.0 if category == "infrastructure" else 0.0, "source": "keyword_router"},
            }
        }

    state = {
        "transcript": transcript,
        "git_diff_snippet": git_diff[:500] if git_diff else "None",
    }
    questions = {
        "issue_category": {
            "type": "choice",
            "instructions": "Classify the spoken developer issue. Prioritize the transcript over Git changes.",
            "criteria": {
                "syntax_error": "Syntax, indentation, or parsing errors.",
                "infrastructure": "Docker, containers, databases, ports, or servers.",
                "logic_bug": "Incorrect output or unexpected behavior.",
                "git_issue": "Git branches, commits, merges, status, or repository problems.",
            },
        },
        "requires_logs": {
            "type": "noul",
            "instructions": "Are server or application logs needed to diagnose this issue?",
        },
    }
    router = router or get_router(config.triage.device)
    start = time.perf_counter()
    result = router.predict(state, questions)
    print(f"[TIMING] LAYA inference: {time.perf_counter() - start:.2f}s")
    return result
