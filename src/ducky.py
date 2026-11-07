import os
import sys
import subprocess
from dotenv import load_dotenv

# Support running as: .venv/bin/python src/ducky.py
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from api.stt import transcribe_audio, STTError
from api.tts import synthesize_audio
from core.config import load_config
from core.context import get_git_diff, get_docker_logs
from core.ignore import IgnoreManager
from core.parser import analyze_incident
from core.triage import triage_incident
from core.debuglog import log_event
import time


def record_audio(output_file: str, duration: int = 5) -> bool:
    print(f"🎙️ Recording for {duration} seconds... Speak your Hinglish bug now!")
    try:
        subprocess.run(
            ["arecord", "-d", str(duration), "-f", "S16_LE", "-c", "1", "-r", "16000", output_file],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        print("✅ Recording complete.")
        return True
    except subprocess.CalledProcessError:
        print("❌ Failed to record audio. Make sure your mic is working.")
    except FileNotFoundError:
        print("❌ 'arecord' command not found. Are you on Linux/ALSA?")
    return False


def main():
    load_dotenv()
    config = load_config()
    os.chdir(config.project_root)
    ignore_manager = IgnoreManager(config.project_root)
    log_event("app", "started")
    print("🦆 RubberDucky initializing...")
    print(f"⚙️ Config: {config.config_path}")

    audio_file = "temp_input.wav"
    output_audio = "temp_output.wav"
    try:
        stage_started = time.perf_counter()
        if not record_audio(audio_file, duration=config.voice.record_seconds):
            log_event("recording", "failed", level="warning")
            return
        log_event("recording", "completed", duration_ms=(time.perf_counter() - stage_started) * 1000)

        print("👂 Transcribing audio with Prisma...")
        stage_started = time.perf_counter()
        try:
            transcript = transcribe_audio(audio_file, language=config.voice.language)
            log_event("stt", "completed", duration_ms=(time.perf_counter() - stage_started) * 1000)
        except STTError as exc:
            log_event("stt", "failed", level="error", duration_ms=(time.perf_counter() - stage_started) * 1000)
            print(f"\n❌ Speech recognition failed: {exc}")
            return

        transcript = ignore_manager.sanitize_context(transcript)
        print(f"\n💬 You said: '{transcript}'")

        stage_started = time.perf_counter()
        git_diff = get_git_diff(repo_path=str(config.project_root))
        log_event("git", "context_collected", duration_ms=(time.perf_counter() - stage_started) * 1000)
        print("\n⚡ Running LAYA Triage...")
        stage_started = time.perf_counter()
        triage_result = triage_incident(transcript, git_diff)
        log_event("triage", "completed", duration_ms=(time.perf_counter() - stage_started) * 1000)
        answers = triage_result.get("answers", {})
        category = answers.get("issue_category", {}).get("choice", "unknown")
        log_probability = answers.get("requires_logs", {}).get("noul", 0.0)
        needs_logs = category == "infrastructure" or log_probability >= 0.70
        print(f"LAYA classified this as: {category.upper()} (Log Prob: {log_probability:.2f})")

        print("\n🔍 Gathering System Context...")
        print("--- Filtered Git Diff Snapshot ---")
        print("\n".join(git_diff.splitlines()[:10]) + "\n...[truncated]" if git_diff else "No Git context available.")

        docker_logs = None
        if needs_logs and category == "infrastructure":
            container_name = input("Docker container name: ").strip()
            if container_name:
                docker_logs = get_docker_logs(container_name)
            else:
                print("No container specified. Skipping Docker logs.")

        print("\n🧠 LLM Parsing Incident...")
        analysis = analyze_incident(
            transcript,
            git_diff=git_diff,
            docker_logs=docker_logs,
            category=category,
        )
        log_event("app", "analysis_completed")
        print("\n📝 --- INCIDENT DIAGNOSIS ---")
        print(analysis.get("diagnosis", "No diagnosis generated."))
        print("------------------------------")

        tts_response = analysis.get("tts_response", "Bhai, kuch samajh nahi aaya.")
        print(f"\n🗣️ Speaking response: '{tts_response}'")
        stage_started = time.perf_counter()
        if synthesize_audio(tts_response, output_path=output_audio, language=config.voice.language):
            log_event("tts", "completed", duration_ms=(time.perf_counter() - stage_started) * 1000)
            print("🔊 Playing response...")
            try:
                subprocess.run(["aplay", output_audio], check=True, stderr=subprocess.DEVNULL)
            except (subprocess.CalledProcessError, FileNotFoundError):
                log_event("playback", "failed", level="warning")
                print("Audio playback unavailable.")
        else:
            log_event("tts", "failed", level="warning", duration_ms=(time.perf_counter() - stage_started) * 1000)
    except KeyboardInterrupt:
        log_event("app", "interrupted", level="warning")
        print("\nRubberDucky interrupted.")
    except Exception as exc:
        log_event("app", "unexpected_error", level="error")
        print(f"RubberDucky error: {type(exc).__name__}")
    finally:
        log_event("app", "finished")
        for filename in (audio_file, output_audio):
            try:
                if os.path.exists(filename):
                    os.remove(filename)
            except OSError:
                pass


if __name__ == "__main__":
    main()
