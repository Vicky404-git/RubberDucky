import os
from gnani.stt import GnaniSTTClient

def transcribe_audio(file_path: str, language: str = "hi-IN") -> str:
    """Takes a .wav file path and returns the Hinglish transcript string."""
    api_key = os.getenv("GNANI_API")
    client = GnaniSTTClient(api_key=api_key)
    
    # We proved this works earlier!
    result = client.transcribe(file_path, language_code=language)
    return result["transcript"]
