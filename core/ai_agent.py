import os
import json
import argparse
import time
from google import genai
from google.genai import types
from dotenv import load_dotenv

# 1. Setup
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    print("❌ ERROR: GEMINI_API_KEY not found.")
    exit(1)

client = genai.Client(api_key=api_key)
TARGET_MODEL = 'gemini-2.5-flash'

def generate_summary(artifact_data: dict):
    title = artifact_data.get("manga_title", "Unknown")
    chapter = artifact_data.get("chapter_number", "Unknown")
    lang = artifact_data.get("source_language", "en")
    raw_text = artifact_data.get("raw_text", "")

    print(f"🧠 AI ({TARGET_MODEL}) is processing Chapter {chapter}...")

    prompt = f"""
    You are a professional Manga researcher. Summarize this raw OCR text from "{title}" Chapter {chapter} (Source: {lang}).
    Translate to English, ignore OCR noise, and output JSON.

    OUTPUT SCHEMA:
    {{
      "chapter_number": "{chapter}",
      "key_events": ["list"],
      "character_updates": "string",
      "lore_and_worldbuilding": "string",
      "ending_cliffhanger": "string"
    }}

    RAW TEXT:
    {raw_text}
    """

    try:
        response = client.models.generate_content(
            model=TARGET_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type='application/json',
            ),
        )
        return json.loads(response.text)
    except Exception as e:
        if "429" in str(e):
            print("\n❌ RATE LIMIT REACHED: You are sending requests too fast for the Free Tier.")
        else:
            print(f"❌ AI Error: {e}")
        return None

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-f", "--file", required=True)
    args = parser.parse_args()

    if not os.path.exists(args.file):
        return

    with open(args.file, 'r', encoding='utf-8') as f:
        artifact = json.load(f)

    summary_json = generate_summary(artifact)

    if summary_json:
        output_dir = "./data/summaries"
        os.makedirs(output_dir, exist_ok=True)
        
        safe_title = "".join([c for c in artifact["manga_title"] if c.isalnum()]).lower()
        filename = f"{safe_title}_ch{artifact['chapter_number']}_summary.json"
        file_path = os.path.join(output_dir, filename)

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(summary_json, f, indent=2, ensure_ascii=False)

        print(f"✨ Summary saved to: {file_path}")

if __name__ == "__main__":
    main()