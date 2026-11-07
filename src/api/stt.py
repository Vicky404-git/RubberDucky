import os
from gnani.stt import GnaniSTTClient


class STTError(Exception):
    """Raised when Prisma transcription cannot be completed."""


def transcribe_audio(file_path: str, language: str = "hi-IN") -> str:
    """Transcribe a WAV file using Gnani Prisma."""

    api_key = os.getenv("GNANI_API")

    if not api_key:
        raise STTError("GNANI_API is missing from your environment.")

    if not os.path.isfile(file_path):
        raise STTError(f"Audio file not found: {file_path}")

    try:
        client = GnaniSTTClient(api_key=api_key)
        result = client.transcribe(file_path, language_code=language)

        if not isinstance(result, dict):
            raise STTError("Prisma returned an unexpected response.")

        transcript = result.get("transcript")

        if not isinstance(transcript, str) or not transcript.strip():
            raise STTError("Prisma returned an empty transcript.")

        return transcript.strip()

    except STTError:
        raise
    except Exception as exc:
        status_code = getattr(exc, "status_code", None)

        if status_code == 504:
            message = "Prisma server timed out (HTTP 504). Try again shortly."
        elif status_code == 429:
            message = "Prisma rate limit reached (HTTP 429). Try again later."
        else:
            message = f"Prisma transcription failed ({type(exc).__name__})."

        raise STTError(message) from exc

