import json
import ollama

# Match the Gemini prompt exactly to ensure consistent DB records
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
    Local AI Worker (Ollama):
    Input: Raw OCR String 
    Output: Dictionary (to be saved by the processor to Postgres)
    """
    if not ocr_text or len(ocr_text.strip()) < 50:
        print("⚠️ OCR text too short/empty for Local AI.")
        return None

    prompt = SUMMARY_PROMPT_TEMPLATE.format(ocr_text=ocr_text)
    
    try:
        # 🚀 Using 'llama3.1' as our narrative engine
        response = ollama.chat(
            model='llama3.1', 
            messages=[{'role': 'user', 'content': prompt}],
            format='json'  # Ollama's native JSON mode
        )
        
        # Ollama returns a dict; we need the content string parsed into a dict
        content = response['message']['content']
        return json.loads(content)
        
    except Exception as e:
        print(f"\n❌ Local AI Error: {e}")
        print("💡 Tip: Ensure 'ollama serve' is running and 'llama3.1' is pulled.")
        return None