import json
import google.generativeai as genai
from core import config

# --- CONFIGURATION ---
genai.configure(api_key=config.GEMINI_API_KEY)

# --- PROMPT TEMPLATES ---
SUMMARY_PROMPT_TEMPLATE = """
You are an expert narrative analyst for the series "Demon Devourer". 
Below is a raw English OCR transcript of a chapter. 

Your goal is to provide a cohesive summary. Because the text is grouped in paragraphs, 
pay close attention to character dialogue and internal monologues.

STRICT JSON OUTPUT:
{{
    "identified_chapter_num": "string",
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
    
    Args:
        ocr_text (str): The raw text extracted via MangaOCR.
        
    Returns:
        dict: A structured dictionary containing identified metadata and summary, 
              or None if the AI call or JSON parsing fails.
    """
    # 1. Initialize the model using the target version from config
    model = genai.GenerativeModel(config.TARGET_MODEL)
    
    # 2. Inject the OCR text into our structured prompt template
    prompt = SUMMARY_PROMPT_TEMPLATE.format(ocr_text=ocr_text)

    try:
        # 3. Request content generation from Gemini
        response = model.generate_content(prompt)
        
        # 4. Clean the response. 
        # LLMs often wrap JSON in Markdown code blocks (```json ... ```); 
        # we strip those to ensure json.loads() doesn't explode.
        raw_output = response.text
        clean_text = raw_output.replace("```json", "").replace("```", "").strip()
        
        # 5. Parse the cleaned string into a Python Dictionary
        return json.loads(clean_text)
        
    except json.JSONDecodeError as je:
        print(f"❌ JSON Parsing Error: The AI returned an invalid format. Raw response: {response.text[:100]}...")
        return None
    except Exception as e:
        print(f"❌ Gemini AI Error: {e}")
        return None

# NOTE: If your 'run_pipeline.py' still calls get_nearest_context or update_manifest,
# make sure to keep those function signatures here to avoid ImportErrors.