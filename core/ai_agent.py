import os
import json
import argparse
import time
from datetime import datetime
from google import genai
from google.genai import types
from dotenv import load_dotenv

# --- CONFIGURATION ---
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=api_key)

TARGET_MODEL = 'gemini-2.5-flash'
SCHEMA_VERSION = "1.0"  # Increment this if you change the JSON structure later

def update_manifest(output_dir, title, safe_title, chapter_num):
    """Maintains a manifest.json to index all available summaries for a title."""
    manifest_path = os.path.join(output_dir, "manifest.json")
    
    # 1. Load existing manifest or create new one
    if os.path.exists(manifest_path):
        with open(manifest_path, 'r', encoding='utf-8') as f:
            manifest = json.load(f)
    else:
        manifest = {
            "manga_title": title,
            "safe_title": safe_title,
            "schema_version": SCHEMA_VERSION,
            "last_updated": "",
            "chapters_summarized": []
        }

    # 2. Update metadata
    manifest["last_updated"] = datetime.now().isoformat()
    
    # 3. Add chapter if not already present and keep list sorted
    if chapter_num not in manifest["chapters_summarized"]:
        manifest["chapters_summarized"].append(float(chapter_num))
        manifest["chapters_summarized"].sort()

    # 4. Save manifest
    with open(manifest_path, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    
    print(f"📄 Manifest updated: {manifest_path}")

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
                temperature=0.1,
            ),
        )
        return json.loads(response.text)
    except Exception as e:
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

    summary_content = generate_summary(artifact)

    if summary_content:
        # Standardized Title Slug
        raw_title = artifact.get("manga_title", "unknown")
        safe_title = "".join([c for c in raw_title if c.isalpha() or c.isspace()]).replace(" ", "_").lower()
        chapter_num = artifact.get("chapter_number", "0")
        
        output_dir = os.path.join("./data/summaries", safe_title)
        os.makedirs(output_dir, exist_ok=True)

        # --- THE ENTERPRISE ENVELOPE ---
        # We wrap the AI output in our own metadata for future-proofing
        final_output = {
            "schema_version": SCHEMA_VERSION,
            "generated_at": datetime.now().isoformat(),
            "model_used": TARGET_MODEL,
            "source_artifact": args.file,
            "summary": summary_content
        }

        file_path = os.path.join(output_dir, f"ch{chapter_num}_summary.json")

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(final_output, f, indent=2, ensure_ascii=False)

        print(f"✨ Summary saved to: {file_path}")
        
        # --- UPDATE MANIFEST ---
        update_manifest(output_dir, raw_title, safe_title, chapter_num)

if __name__ == "__main__":
    main()