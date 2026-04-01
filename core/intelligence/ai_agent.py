import json
from google import genai
from google.genai import types
from core import config

# --- CUSTOM EXCEPTIONS ---
class RateLimitExhaustedError(Exception):
    """Signals that we've hit the Gemini API spending cap or rate limit."""
    pass

# --- CONFIGURATION ---
client = genai.Client(api_key=config.GEMINI_API_KEY)

# --- PROMPT TEMPLATES ---
# I added 'key_insights' and 'tone' to make your summaries more robust for the DB
SUMMARY_PROMPT_TEMPLATE = """
You are an expert manga/manhwa narrative analyst. 
Analyze the provided OCR text and generate a concise, spoiler-free chapter summary.

JSON STRUCTURE REQUIRED:
{{
    "summary": "A 3-5 sentence narrative of the main plot points.",
    "key_moments": ["Event A", "Event B", "Event C"],
    "characters_present": ["Character name or description"],
    "tone": "e.g., Action-heavy, Comedic, Melancholic"
}}

OCR DATA:
{ocr_text}
"""

def generate_summary(ocr_text: str):
    """
    Pure AI Worker: 
    Input: Raw OCR String 
    Output: Dictionary (to be saved by the processor to Postgres)
    """
    if not ocr_text or len(ocr_text.strip()) < 50:
        return None

    prompt = SUMMARY_PROMPT_TEMPLATE.format(ocr_text=ocr_text)

    try:
        response = client.models.generate_content(
            model=config.TARGET_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.7,  # Added for better narrative flow
                top_p=0.95,
            )
        )
        
        # 1. Check if the response actually contains text
        if not response.text:
            print("⚠️ Gemini returned an empty response (likely blocked by safety filters).")
            return None

        # 2. Parse the JSON string into a Python dict
        ai_data = json.loads(response.text)
        
        # 3. Basic Validation: Ensure the keys we expect actually exist
        required_keys = ["summary", "key_moments", "characters_present"]
        if not all(k in ai_data for k in required_keys):
            print("⚠️ AI JSON missing required keys. Raw output:", response.text)
            return None

        return ai_data
        
    except json.JSONDecodeError as je:
        print(f"❌ AI returned invalid JSON: {je}")
        return None
    except Exception as e:
        error_msg = str(e).upper()
        if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg:
            raise RateLimitExhaustedError("Gemini API: Resource Exhausted (429).") from e
            
        print(f"❌ Gemini AI Error: {e}")
        return None