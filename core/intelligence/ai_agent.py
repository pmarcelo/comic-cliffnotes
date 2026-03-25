import json
import google.generativeai as genai
from core import config

# --- CONFIGURATION ---
genai.configure(api_key=config.GEMINI_API_KEY)

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
    model = genai.GenerativeModel(config.TARGET_MODEL)
    prompt = SUMMARY_PROMPT_TEMPLATE.format(ocr_text=ocr_text)

    try:
        # 🚀 THE SILVER BULLET: Force the API to return strictly valid JSON
        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                response_mime_type="application/json",
            )
        )
        
        # Because we enforced application/json, response.text is guaranteed to be clean JSON
        return json.loads(response.text)
        
    except json.JSONDecodeError as je:
        # This should theoretically never trigger now, but kept for absolute safety
        print(f"❌ JSON Parsing Error: {je}")
        print(f"Raw Output: {response.text[:200]}")
        return None
    except Exception as e:
        print(f"❌ Gemini AI Error: {e}")
        return None

# Keep any other helper functions (get_nearest_context, etc.) below this line