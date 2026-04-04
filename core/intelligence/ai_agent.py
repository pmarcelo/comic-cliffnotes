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
SUMMARY_PROMPT_TEMPLATE = """
You are an expert manga/manhwa narrative analyst. 
Analyze the provided OCR text and generate a structured, spoiler-free chapter summary. 

The OCR data may contain fragments, vertical text artifacts, or page numbers. Ignore these and focus only on dialogue and narrative descriptions.

CRITICAL: This data will be used to automatically detect multi-chapter story arcs later. You must be highly precise about location changes, newly introduced characters, and shifting character motivations.

You MUST return a valid JSON object with these exact keys:
{{
    "chapter_summary": "A 3-5 sentence narrative of the main plot points.",
    "settings": ["List of distinct locations where the chapter takes place"],
    "characters": {{
        "active": ["List of established characters who play a role"],
        "introduced": ["Any characters appearing or named for the VERY FIRST time"]
    }},
    "key_events": ["Event A", "Event B", "Event C"],
    "current_objective": "What is the primary goal or immediate conflict driving the protagonist right now?",
    "unresolved_threads": ["Any cliffhangers, ongoing battles, or mysteries carrying over to the next chapter"]
}}

OCR DATA:
{ocr_text}
"""

# --- HELPER METHODS ---
def _extract_usage_stats(response) -> dict:
    """
    Safely extracts token usage metadata from the Gemini response object.
    Returns a dictionary of token counts, or zeroes if unavailable.
    """
    try:
        usage = response.usage_metadata
        if usage:
            return {
                "prompt_tokens": getattr(usage, 'prompt_token_count', 0),
                "candidates_tokens": getattr(usage, 'candidates_token_count', 0),
                "total_tokens": getattr(usage, 'total_token_count', 0)
            }
    except AttributeError:
        # Failsafe in case the response object is malformed
        pass 
    
    return {"prompt_tokens": 0, "candidates_tokens": 0, "total_tokens": 0}

# --- MAIN WORKER ---
# ---> NEW: Added model_name parameter with fallback <---
def generate_summary(ocr_text: str, model_name: str = getattr(config, 'DEFAULT_MODEL', 'gemini-3.1-flash-lite-preview')):
    """
    Pure AI Worker: 
    Input: Raw OCR String 
    Output: Dictionary (to be saved by the processor to Postgres)
    """
    if not ocr_text or len(ocr_text.strip()) < 50:
        return None

    prompt = SUMMARY_PROMPT_TEMPLATE.format(ocr_text=ocr_text)

    try:
        # ---> NEW: Use the dynamically passed model parameter <---
        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.7,  
                top_p=0.95,
            )
        )
        
        # 1. Extract Token Usage using the helper method
        token_info = _extract_usage_stats(response)

        # 2. Check if the response actually contains text
        if not response.text:
            print("⚠️ Gemini returned an empty response (likely blocked by safety filters).")
            return None

        # 3. Parse the JSON string into a Python dict
        ai_data = json.loads(response.text)
        
        # 4. Basic Validation: Ensure the keys we expect actually exist
        required_keys = [
            "chapter_summary", 
            "settings", 
            "characters", 
            "key_events", 
            "current_objective", 
            "unresolved_threads"
        ]
        if not all(k in ai_data for k in required_keys):
            print("⚠️ AI JSON missing required keys. Raw output:", response.text)
            return None

        # 5. Attach usage stats to the final payload for Streamlit/DB tracking
        ai_data["_usage_stats"] = token_info

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