import os
import subprocess
import sys
import time

from dotenv import load_dotenv

# Support running as: .venv/bin/python src/ducky.py
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from api.stt import STTError, transcribe_audio
from core.config import load_config
from core.debuglog import log_event
from core.ignore import IgnoreManager
from core.pipeline import run_debug_pipeline


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
    git_text = ""

    def on_event(event_type: str, payload: dict) -> None:
        nonlocal git_text
        if event_type == "git_context_collected":
            git_text = str(payload.get("git_text", ""))
        elif event_type == "triage_started":
            print("\n⚡ Running LAYA Triage...")
        elif event_type == "triage_completed":
            category = str(payload.get("category", "unknown"))
            probability = float(payload.get("log_probability", 0.0) or 0.0)
            print(f"LAYA classified this as: {category.upper()} (Log Prob: {probability:.2f})")
            print("\n🔍 Gathering System Context...")
            print("--- Filtered Git Diff Snapshot ---")
            if git_text:
                print("\n".join(git_text.splitlines()[:10]) + "\n...[truncated]")
            else:
                print("No Git context available.")
        elif event_type == "llm_started":
            print("\n🧠 LLM Parsing Incident...")
        elif event_type == "llm_completed":
            print("\n📝 --- INCIDENT DIAGNOSIS ---")
            print(payload.get("diagnosis", "No diagnosis generated."))
            print("------------------------------")
            print(f"\n🗣️ Speaking response: '{payload.get('spoken_response', '')}'")
            log_event("app", "analysis_completed")
        elif event_type == "llm_failed":
            print(f"\n❌ AI diagnosis failed: {payload.get('message', 'Unknown error.')}")

    def docker_container_provider() -> str | None:
        container = input("Docker container name: ").strip()
        if not container:
            print("No container specified. Skipping Docker logs.")
        return container or None

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

        result = run_debug_pipeline(
            transcript,
            config=config,
            repo_path=config.project_root,
            docker_container_provider=docker_container_provider,
            output_audio_path=output_audio,
            on_event=on_event,
            infrastructure_logs_only=True,
        )

        if result.error is not None:
            log_event("app", "analysis_failed", level="warning", code=result.error.status_code)
        elif result.audio_path is not None:
            print("🔊 Playing response...")
            try:
                subprocess.run(
                    ["aplay", str(result.audio_path)],
                    check=True,
                    stderr=subprocess.DEVNULL,
                )
            except (subprocess.CalledProcessError, FileNotFoundError):
                log_event("playback", "failed", level="warning")
                print("Audio playback unavailable.")
        elif result.tts_error:
            log_event("tts", "failed", level="warning")
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
