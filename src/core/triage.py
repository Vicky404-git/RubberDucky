import os
from laya import Router

# Force LAYA to use the cached model and skip the network check
os.environ["HF_HUB_OFFLINE"] = "1"

print("⏳ Loading LAYA Triage Engine (Offline Cache)...")
# Initialize silently without the progress bars
router = Router(preload=True, device="cpu")

def triage_incident(transcript: str, git_diff: str = "") -> dict:
    """Uses LAYA to instantly classify the type of incident."""
    
    # The state is the context LAYA will read
    state = {
        "transcript": transcript,
        "git_diff_snippet": git_diff[:500] if git_diff else "None"
    }

    # The questions we want LAYA to answer deterministically
    questions = {
        "issue_category": {
            "type": "choice",
            "instructions": "Based on the transcript and git diff, what kind of issue is the developer facing?",
            "criteria": {
                "syntax_error": "Typos, missing parentheses, or basic code structure issues.",
                "infrastructure": "Docker, database, ports, or server connection issues.",
                "logic_bug": "The code runs but produces the wrong output or unexpected behavior.",
                "git_issue": "Merge conflicts, commit issues, or branch problems."
            }
        },
        "requires_logs": {
            "type": "noul",
            "instructions": "Does this issue look like it requires server logs to diagnose properly?"
        }
    }

    # Run the local inference
    print("🧠 LAYA classifying incident...")
    result = router.predict(state, questions)
    
    return result
