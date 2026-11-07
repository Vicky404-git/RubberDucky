import os
import requests

def synthesize_audio(text: str, output_path: str = "output.wav") -> bool:
    """Takes a Hinglish string and saves the Timbre TTS audio to output_path."""
    api_key = os.getenv("GNANI_API")
    url = "https://api.vachana.ai/api/v1/tts/inference"
    
    headers = {
        "Content-Type": "application/json",
        "X-API-Key-ID": api_key,
    }
    
    payload = {
        "text": text,
        "voice": "Nalini",
        "model": "timbre-v2.5",
        "language": "hi-IN",
        "speed": 1.0,
        "audio_config": {
            "sample_rate": 48000,
            "num_channels": 1,
            "sample_width": 2,
            "encoding": "linear_pcm",
            "container": "wav"
        }
    }
    
    # We proved this raw REST call works earlier!
    response = requests.post(url, headers=headers, json=payload)
    
    if response.status_code == 200:
        with open(output_path, "wb") as f:
            f.write(response.content)
        return True
    
    print(f"TTS Error: {response.status_code} - {response.text}")
    return False
