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
Analyze the provided OCR text and generate a structured chapter summary while updating the ongoing World State (Living Summary).

{context_block}

OCR DATA FOR CURRENT CHAPTER:
{ocr_text}

---
INSTRUCTIONS:
1. NARRATIVE: Focus only on dialogue and narrative descriptions. Ignore OCR artifacts.
2. STATE EVOLUTION: Review the "Living Summary" (if provided). 
   - Update 'story_so_far' by integrating new events while keeping it concise (max 300 words).
   - Update 'meta' if the primary location or objective has shifted.
   - Update 'character_bank': Update statuses or add new characters. Remove characters not seen for 20+ chapters to save space.

You MUST return a valid JSON object with these exact keys:
{{
    "chapter_summary": "A 3-5 sentence narrative of this specific chapter's plot points.",
    "settings": ["List of distinct locations in this chapter"],
    "characters": {{
        "active": ["Established characters in this chapter"],
        "introduced": ["Characters appearing for the VERY FIRST time"]
    }},
    "key_events": ["Event A", "Event B"],
    "current_objective": "Immediate goal driving the protagonist right now.",
    "unresolved_threads": ["Cliffhangers or mysteries"],
    "updated_living_summary": {{
        "meta": {{
            "current_location": "String",
            "active_objective": "String"
        }},
        "story_so_far": "The updated narrative prose (concise summary of everything to date)",
        "character_bank": [
            {{"name": "String", "status": "String", "last_seen_chapter": int}}
        ]
    }}
}}
"""

# --- HELPER METHODS ---
def _extract_usage_stats(response) -> dict:
    try:
        usage = response.usage_metadata
        if usage:
            return {
                "prompt_tokens": getattr(usage, 'prompt_token_count', 0),
                "candidates_tokens": getattr(usage, 'candidates_token_count', 0),
                "total_tokens": getattr(usage, 'total_token_count', 0)
            }
    except AttributeError:
        pass 
    return {"prompt_tokens": 0, "candidates_tokens": 0, "total_tokens": 0}

# --- MAIN WORKER ---
def generate_summary(ocr_text: str, living_summary: dict = None, model_name: str = None):
    """
    Stateful AI Worker: 
    Input: Raw OCR + Previous Living Summary JSON
    Output: Dictionary containing Chapter Details AND Updated Living Summary
    """
    if not model_name:
        model_name = getattr(config, 'DEFAULT_MODEL', 'gemini-3.1-flash-lite-preview')

    if not ocr_text or len(ocr_text.strip()) < 50:
        return None

    # Handle the context block
    context_block = "No previous context. This is the start of the processing run."
    if living_summary:
        context_block = f"CURRENT WORLD STATE (LIVING SUMMARY):\n{json.dumps(living_summary, indent=2)}"

    prompt = SUMMARY_PROMPT_TEMPLATE.format(
        context_block=context_block,
        ocr_text=ocr_text
    )

    try:
        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.7,  
                top_p=0.95,
            )
        )
        
        token_info = _extract_usage_stats(response)

        if not response.text:
            return None

        ai_data = json.loads(response.text)
        
        # Validation
        required_keys = ["chapter_summary", "updated_living_summary"]
        if not all(k in ai_data for k in required_keys):
            print("⚠️ AI JSON missing required keys.")
            return None

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