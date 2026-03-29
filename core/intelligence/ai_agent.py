import json
from google import genai
from google.genai import types
from core import config

# --- CUSTOM EXCEPTIONS ---

class RateLimitExhaustedError(Exception):
    """Signals that we've hit the Gemini API spending cap or rate limit."""
    pass

# --- CONFIGURATION ---
# Initializing with the modern SDK client
client = genai.Client(api_key=config.GEMINI_API_KEY)

# --- PROMPT TEMPLATES ---
SUMMARY_PROMPT_TEMPLATE = """
You are an expert narrative analyst. Below is a raw English OCR transcript of a chapter. 

Your goal is to provide a cohesive summary based on the dialogue and narrative.

You MUST return a valid JSON object with the exact keys below:
{{
    "summary": "A 3-5 sentence narrative of what happened.",
    "key_moments": ["First event", "Second event", "Third event"],
    "characters_present": ["Name 1", "Name 2"]
}}

OCR DATA:
{ocr_text}
"""

def generate_summary(ocr_text):
    """
    Sends OCR text to Gemini. 
    Triggers RateLimitExhaustedError on 429s to halt the pipeline.
    """
    prompt = SUMMARY_PROMPT_TEMPLATE.format(ocr_text=ocr_text)

    try:
        # 🚀 Modern SDK Method with JSON mode enforced
        response = client.models.generate_content(
            model=config.TARGET_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
            )
        )
        
        # response.text is guaranteed valid JSON due to response_mime_type
        return json.loads(response.text)
        
    except Exception as e:
        error_msg = str(e).upper()
        
        # 🛑 THE CIRCUIT BREAKER: Check for rate limits
        if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg:
            print(f"\n🛑 API QUOTA EXCEEDED: {e}")
            raise RateLimitExhaustedError("Gemini API: Resource Exhausted (429).") from e
            
        # Log other errors (network, 500s, etc.) but don't necessarily kill the daemon
        print(f"❌ Gemini AI Error: {e}")
        return None

# Helper functions for future context-awareness can be added here