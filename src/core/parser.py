import os
import json
from openai import OpenAI
from typing import Dict

def analyze_incident(transcript: str, git_diff: str = "", docker_logs: str = "") -> Dict[str, str]:
    """
    Takes the Hinglish transcript and system context, sends it to OpenRouter,
    and returns a diagnosis and a Hinglish TTS response.
    """
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        print("⚠️ OPENROUTER_API_KEY not found. Returning fallback response.")
        return {
            "diagnosis": "Missing OpenRouter API Key.",
            "tts_response": "Bhai, OpenRouter ki API key missing hai environment mein."
        }

    # OpenRouter uses the OpenAI client format
    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
    )
    
    # Construct the context payload
    context_payload = ""
    if git_diff and git_diff != "No uncommitted changes.":
        # Truncate diff to ~30,000 characters just to be safe, though Liquid has 256K context
        truncated_diff = git_diff[:30000] + "\n...[DIFF TRUNCATED]" if len(git_diff) > 30000 else git_diff
        context_payload += f"\n[CURRENT GIT DIFF]\n{truncated_diff}\n"
    if docker_logs:
        context_payload += f"\n[DOCKER LOGS]\n{docker_logs}\n"

    system_prompt = """
    You are RubberDucky, a highly technical, slightly sarcastic Indian backend developer. 
    Your colleague is debugging an issue and speaking to you in natural Hinglish.
    
    TASK:
    1. Read the terminal context to find the root cause of their complaint.
    2. Respond with a concise, technically accurate fix.
    
    OUTPUT FORMAT:
    Provide your response as a valid JSON object with exactly two keys:
    - "diagnosis": A short Markdown summary of the bug and the fix (for the terminal).
    - "tts_response": A natural, conversational Hinglish sentence (using ONLY standard Hindi written in English script and common English tech terms). NEVER invent words like "mucha" or "putein". Keep it natural like: "Bhai, diff dekha maine. Tune API key pass nahi ki hai function mein."
    
    CRITICAL: Output ONLY valid JSON.
    """

    user_prompt = f"[USER SPOKEN COMPLAINT]\n{transcript}\n{context_payload}"

    try:
        response = client.chat.completions.create(
            # Using Liquid's free, long-context reasoning model available on OpenRouter
            model="liquid/lfm-3-1.7b:free", 
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
        )
        
        # Clean the response in case the model returns markdown ticks despite instructions
        raw_content = response.choices[0].message.content.strip()
        if raw_content.startswith("```json"):
            raw_content = raw_content[7:]
        if raw_content.endswith("```"):
            raw_content = raw_content[:-3]
            
        result = json.loads(raw_content)
        return result

    except Exception as e:
        print(f"OpenRouter API Error: {e}")
        return {
            "diagnosis": "API Request Failed.",
            "tts_response": "Bhai, LLM API fail ho gayi. Connection check kar."
        }
