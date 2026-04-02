import json
from google import genai
from google.genai import types
from core import config

class RateLimitExhaustedError(Exception):
    pass

client = genai.Client(api_key=config.GEMINI_API_KEY)

ARC_PROMPT_TEMPLATE = """
You are an expert manga/manhwa Narrative Editor. 
I will provide you with a JSON list of sequential chapter summaries and their metadata. 

Your task is to analyze this data, identify the natural "Story Arcs", and synthesize them. 

PREVIOUS CONTEXT:
{previous_context}
(If there is an ongoing arc above, the first chapters in your batch belong to it. You must either conclude it and move it to 'completed_arcs', or if it is STILL unresolved by the end of this batch, update its summary and return it as the new 'ongoing_arc'.)

HOW TO DETECT ARC BOUNDARIES:
- Look for major shifts in the "current_objective" or massive changes in "settings".
- Look at "unresolved_threads". Do NOT end an arc if a major battle or cliffhanger is active.

You MUST return a valid JSON object with these exact keys:
{{
    "completed_arcs": [
        {{
            "arc_title": "String",
            "start_chapter": Integer,
            "end_chapter": Integer,
            "arc_summary": "Comprehensive 2-3 paragraph recap.",
            "core_cast": ["Character A", "Character B"],
            "status_quo_shift": "One sentence impact."
        }}
    ],
    "ongoing_arc": {{
        "arc_title": "String",
        "start_chapter": Integer,
        "arc_summary": "Summary of events SO FAR in this unfinished arc.",
        "core_cast": ["Character A"]
    }} // NOTE: Set this to null if the batch ends perfectly on a clean arc boundary.
}}

CHAPTER DATA BATCH:
{chapter_batch_json}
"""

def generate_arc_summaries(chapter_batch_data: list, previous_ongoing_arc=None):
    if not chapter_batch_data:
        return None

    batch_str = json.dumps(chapter_batch_data, indent=2, ensure_ascii=False)
    
    # Format the previous context if it exists
    prev_context_str = "None. This is the start of the series."
    if previous_ongoing_arc:
        prev_context_str = f"ONGOING ARC CARRIED OVER:\n{json.dumps(previous_ongoing_arc, indent=2)}"

    prompt = ARC_PROMPT_TEMPLATE.format(
        previous_context=prev_context_str,
        chapter_batch_json=batch_str
    )

    try:
        response = client.models.generate_content(
            model=config.TARGET_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.7,
            )
        )
        
        if not response.text:
            return None

        ai_data = json.loads(response.text)
        return ai_data
        
    except json.JSONDecodeError as je:
        print(f"❌ AI returned invalid JSON during Arc Synthesis: {je}")
        return None
    except Exception as e:
        if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
            raise RateLimitExhaustedError("Gemini API: Resource Exhausted (429).") from e
        print(f"❌ Gemini Arc AI Error: {e}")
        return None