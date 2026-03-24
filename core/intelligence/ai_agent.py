import google.generativeai as genai
from core import config
import json

genai.configure(api_key=config.GEMINI_API_KEY)

def generate_summary(ocr_text):
    """
    Sends OCR text to Gemini. 
    Returns a JSON object with the actual chapter identity and the summary.
    """
    model = genai.GenerativeModel(config.TARGET_MODEL)
    
    prompt = f"""
    You are a professional manga librarian. Analyze the following OCR text from a manga chapter.
    
    TASK:
    1. Identify the ACTUAL Chapter Number (e.g., "1", "42.5").
    2. Identify the Chapter Title if present (e.g., "The Beginning").
    3. Provide a concise narrative summary of the events.
    4. List key characters appearing in this chapter.

    OUTPUT FORMAT (STRICT JSON):
    {{
        "identified_chapter_num": "string",
        "identified_title": "string",
        "summary": "string",
        "characters": ["name1", "name2"]
    }}

    OCR TEXT:
    {ocr_text}
    """

    try:
        response = model.generate_content(prompt)
        # Clean up the response in case Gemini adds ```json markdown
        clean_text = response.text.replace("```json", "").replace("```", "").strip()
        return json.loads(clean_text)
    except Exception as e:
        print(f"❌ AI Error: {e}")
        return None