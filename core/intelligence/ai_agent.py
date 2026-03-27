import json
from google import genai
from google.genai import types
from core import config

# --- CONFIGURATION ---
# Initialize the client with the new SDK structure
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
    Sends OCR text to the Gemini model to identify chapter metadata and generate a summary.
    """
    prompt = SUMMARY_PROMPT_TEMPLATE.format(ocr_text=ocr_text)

    try:
        # 🚀 THE NEW SDK METHOD: Force the API to return strictly valid JSON
        response = client.models.generate_content(
            model=config.TARGET_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
            )
        )
        
        # Because we enforced application/json, response.text is guaranteed to be clean JSON
        return json.loads(response.text)
        
    except json.JSONDecodeError as je:
        # This should theoretically never trigger now, but kept for absolute safety
        print(f"❌ JSON Parsing Error: {je}")
        if hasattr(response, 'text'):
            print(f"Raw Output: {response.text[:200]}")
        return None
    except Exception as e:
        print(f"❌ Gemini AI Error: {e}")
        # 🚀 NEW: If it's a quota/rate limit error, throw it back to the orchestrator!
        if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
            raise e
        return None

# Keep any other helper functions (get_nearest_context, etc.) below this line