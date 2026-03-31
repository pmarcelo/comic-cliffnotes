import json
import ollama

SUMMARY_PROMPT_TEMPLATE = """
You are an expert narrative analyst. Below is a raw English OCR transcript of a manga chapter. 
Provide a cohesive summary.

You MUST return a valid JSON object with these exact keys:
{{
    "summary": "A 3-5 sentence narrative of what happened.",
    "key_moments": ["First event", "Second event", "Third event"],
    "characters_present": ["Name 1", "Name 2"]
}}

OCR DATA:
{ocr_text}
"""

def generate_summary(ocr_text):
    prompt = SUMMARY_PROMPT_TEMPLATE.format(ocr_text=ocr_text)
    
    try:
        response = ollama.chat(
            model='llama3.1', 
            messages=[{'role': 'user', 'content': prompt}],
            format='json'  # 🚀 Ollama natively forces JSON format!
        )
        
        return json.loads(response['message']['content'])
        
    except Exception as e:
        print(f"\n❌ Local AI Error: {e}")
        print("💡 Make sure the Ollama app is running in the background!")
        return None