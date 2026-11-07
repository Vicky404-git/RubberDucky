
import os
import wave
import requests


TTS_URL = "https://api.vachana.ai/api/v1/tts/inference"


def synthesize_audio(
    text: str,
    output_path: str = "output.wav",
) -> bool:
    """Generate speech using Gnani Timbre and save it as WAV."""

    api_key = os.getenv("GNANI_API")

    if not api_key:
        print("TTS Error: GNANI_API is missing.")
        return False

    if not isinstance(text, str) or not text.strip():
        print("TTS Error: Empty text supplied.")
        return False

    headers = {
        "Content-Type": "application/json",
        "X-API-Key-ID": api_key,
    }

    payload = {
        "text": text.strip(),
        "voice": "Nalini",
        "model": "timbre-v2.5",
        "language": "hi-IN",
        "speed": 1.0,
        "audio_config": {
            "sample_rate": 48000,
            "num_channels": 1,
            "sample_width": 2,
            "encoding": "linear_pcm",
            "container": "wav",
        },
    }

    try:
        response = requests.post(
            TTS_URL,
            headers=headers,
            json=payload,
            timeout=(5, 45),
        )

        if response.status_code != 200:
            print(
                f"TTS HTTP Error: {response.status_code} - "
                f"{response.text[:300]}"
            )
            return False

        audio_data = response.content

        # WAV files normally start with RIFF and contain WAVE at offset 8.
        if (
            len(audio_data) < 44
            or audio_data[:4] != b"RIFF"
            or audio_data[8:12] != b"WAVE"
        ):
            print("TTS Error: API returned invalid WAV audio.")
            return False

        with open(output_path, "wb") as audio_file:
            audio_file.write(audio_data)

        # Validate that the WAV can actually be opened.
        with wave.open(output_path, "rb") as wav_file:
            if wav_file.getnframes() <= 0:
                raise ValueError("WAV contains no audio frames.")

        return True

    except requests.Timeout:
        print("TTS Error: Request timed out.")
        return False

    except requests.ConnectionError:
        print("TTS Error: Could not connect to Gnani.")
        return False

    except requests.RequestException as exc:
        print(f"TTS Request Error: {type(exc).__name__}")
        return False

    except (OSError, wave.Error, ValueError) as exc:
        print(f"TTS Audio Error: {exc}")

        if os.path.exists(output_path):
            os.remove(output_path)

        return False

