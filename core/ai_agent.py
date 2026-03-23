import os
import json
import argparse
from datetime import datetime
from google import genai
from google.genai import types
from core import config  # Import our SSoT

# 1. AI Setup from Config
client = genai.Client(api_key=config.GEMINI_API_KEY)

def update_manifest(title, slug, chapter_num, paths):
    """Maintains a manifest.json to index all available summaries."""
    manifest_path = paths["manifest"]
    
    if manifest_path.exists():
        with open(manifest_path, 'r', encoding='utf-8') as f:
            manifest = json.load(f)
    else:
        manifest = {
            "manga_title": title,
            "safe_title": slug,
            "schema_version": config.SCHEMA_VERSION,
            "last_updated": "",
            "chapters_summarized": []
        }

    manifest["last_updated"] = datetime.now().isoformat()
    
    if float(chapter_num) not in manifest["chapters_summarized"]:
        manifest["chapters_summarized"].append(float(chapter_num))
        manifest["chapters_summarized"].sort()

    with open(manifest_path, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    
    print(f"📄 Manifest updated: {manifest_path}")

def generate_summary(artifact_data: dict):
    title = artifact_data.get("manga_title", "Unknown")
    chapter = artifact_data.get("chapter_number", "Unknown")
    lang = artifact_data.get("source_language", "en")
    raw_text = artifact_data.get("raw_text", "")

    print(f"🧠 AI ({config.TARGET_MODEL}) is processing Chapter {chapter}...")

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
            model=config.TARGET_MODEL,
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

    # Ingest the artifact
    if not os.path.exists(args.file): return

    with open(args.file, 'r', encoding='utf-8') as f:
        artifact = json.load(f)

    # Get paths from our central config
    title = artifact.get("manga_title", "unknown")
    chapter_num = artifact.get("chapter_number", "0")
    paths = config.get_paths(title, str(chapter_num))
    slug = config.get_safe_title(title)

    summary_content = generate_summary(artifact)

    if summary_content:
        # The Enterprise Envelope
        final_output = {
            "schema_version": config.SCHEMA_VERSION,
            "generated_at": datetime.now().isoformat(),
            "model_used": config.TARGET_MODEL,
            "source_artifact": str(args.file),
            "summary": summary_content
        }

        with open(paths["summary"], "w", encoding="utf-8") as f:
            json.dump(final_output, f, indent=2, ensure_ascii=False)

        print(f"✨ Summary saved to: {paths['summary']}")
        update_manifest(title, slug, chapter_num, paths)

if __name__ == "__main__":
    main()