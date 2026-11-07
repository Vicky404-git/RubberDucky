import sys
import os
import subprocess
from dotenv import load_dotenv

# Ensure we can import from the 'src' directory correctly
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from api.stt import transcribe_audio
from api.tts import synthesize_audio
from core.context import get_git_diff, get_docker_logs
from core.parser import analyze_incident

def record_audio(output_file: str, duration: int = 5):
    """A quick helper to record audio from the terminal using ALSA/arecord (Linux)."""
    print(f"🎙️ Recording for {duration} seconds... Speak your Hinglish bug now!")
    try:
        subprocess.run(
            ["arecord", "-d", str(duration), "-f", "S16_LE", "-c", "1", "-r", "16000", output_file],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        print("✅ Recording complete.")
        return True
    except subprocess.CalledProcessError:
        print("❌ Failed to record audio. Make sure your mic is working.")
        return False
    except FileNotFoundError:
        print("❌ 'arecord' command not found. Are you on Linux/ALSA?")
        return False

def main():
    # Load the .env file so the Gnani and Groq SDKs can find their keys
    load_dotenv()
    
    print("🦆 RubberDucky initializing...")
    
    # 1. Record the User's Spoken Complaint
    audio_file = "temp_input.wav"
    if not record_audio(audio_file, duration=5):
        sys.exit(1)

    # 2. Transcribe to Hinglish using Gnani Prisma
    print("👂 Transcribing audio with Prisma...")
    transcript = transcribe_audio(audio_file)
    print(f"\n💬 You said: '{transcript}'")

    # 3. Gather System Context (The "Glue")
    print("\n🔍 Gathering System Context...")
    git_diff = get_git_diff()
    print("--- Git Diff Snapshot ---")
    
    if git_diff and git_diff != "No uncommitted changes.":
        print("\n".join(git_diff.split("\n")[:10]) + "\n...[truncated]")
    else:
        print(git_diff)

    # 4. Analyze the Incident with the LLM Brain
    print("\n🧠 LLM Parsing Incident...")
    analysis = analyze_incident(transcript, git_diff=git_diff)
    
    print("\n📝 --- INCIDENT DIAGNOSIS ---")
    print(analysis.get("diagnosis", "No diagnosis generated."))
    print("------------------------------")
    
    # 5. Speak the Solution using Gnani Timbre
    tts_response = analysis.get("tts_response", "Bhai, kuch samajh nahi aaya.")
    print(f"\n🗣️ Speaking response: '{tts_response}'")
    
    output_audio = "temp_output.wav"
    if synthesize_audio(tts_response, output_path=output_audio):
        print("🔊 Playing response...")
        try:
            subprocess.run(["aplay", output_audio], check=True, stderr=subprocess.DEVNULL)
        except Exception:
            pass
            
    # Cleanup temporary files
    for f in [audio_file, output_audio]:
        if os.path.exists(f):
            os.remove(f)

if __name__ == "__main__":
    main()
