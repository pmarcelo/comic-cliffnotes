import os
import json
import argparse
from datetime import datetime
from google import genai
from google.genai import types
from core import config, helpers

client = genai.Client(api_key=config.GEMINI_API_KEY)

def get_nearest_context(paths, current_ch: float):
    manifest = helpers.load_json(paths["manifest"])
    if not manifest: return None, False

    past_chapters = sorted([c for c in manifest.get("chapters_summarized", []) if c < current_ch], reverse=True)
    if not past_chapters: return None, False

    nearest_ch = past_chapters[0]
    is_gap = (current_ch - nearest_ch) > 1.1 

    prev_summary_path = paths["title_dir"] / f"ch{nearest_ch}_summary.json"
    prev_data = helpers.load_json(prev_summary_path)
    
    if prev_data:
        content = prev_data.get("summary", {})
        events = ", ".join(content.get("key_events", []))
        cliff = content.get("ending_cliffhanger", "N/A")
        return f"PREVIOUSLY (Ch {nearest_ch}): {events}. LAST CLIFFHANGER: {cliff}", is_gap

    return None, False

def update_manifest(title, slug, chapter_num, paths):
    manifest = helpers.load_json(paths["manifest"]) or {
        "manga_title": title, "safe_title": slug,
        "schema_version": config.SCHEMA_VERSION, "chapters_summarized": []
    }

    manifest["last_updated"] = datetime.now().isoformat()
    if float(chapter_num) not in manifest.get("chapters_summarized", []):
        if "chapters_summarized" not in manifest:
            manifest["chapters_summarized"] = []
        manifest["chapters_summarized"].append(float(chapter_num))
        manifest["chapters_summarized"].sort()

    helpers.save_json(manifest, paths["manifest"])
    print(f"📄 Manifest updated: {paths['manifest']}")

def generate_summary(artifact_data: dict, context_memory: str = None, is_gap: bool = False):
    title = artifact_data.get("manga_title", "Unknown")
    chapter = artifact_data.get("chapter_number", "Unknown")
    lang = artifact_data.get("source_language", "en")
    raw_text = artifact_data.get("raw_text", "")

    # Build the memory block and gap warnings
    memory_header = f"\n[STORY CONTEXT]\n{context_memory}\n" if context_memory else ""
    gap_warning = "\n⚠️ NOTE: There is a gap in the chapters provided. Bridge the narrative carefully.\n" if is_gap else ""

    print(f"🧠 AI ({config.TARGET_MODEL}) is processing Chapter {chapter}...")

    prompt = f"""
    You are a professional Manga researcher and storyteller. Summarize this raw OCR text from "{title}" Chapter {chapter}.
    {memory_header}{gap_warning}
    
    Translate to English, ignore OCR noise, and output JSON.
    Maintain continuity with characters and terminology from the context provided.

    OUTPUT SCHEMA:
    {{
      "chapter_number": "{chapter}",
      "narrative_summary": "string (A cohesive, engaging 3-4 sentence human-readable story recap of the chapter)",
      "key_events": ["list (bullet points of specific actions)"],
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
                temperature=0.2, # slightly bumped to 0.2 to give the narrative summary a bit more storytelling flair
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

    artifact = helpers.load_json(args.file)
    if not artifact: return

    title = artifact.get("manga_title", "unknown")
    chapter_num = artifact.get("chapter_number", "0")
    paths = helpers.get_paths(title, str(chapter_num))

    # --- NARRATIVE MEMORY STEP ---
    context, gap_detected = get_nearest_context(paths, float(chapter_num))

    # Generate summary with injected memory
    summary_content = generate_summary(artifact, context_memory=context, is_gap=gap_detected)

    if summary_content:
        final_output = {
            "schema_version": config.SCHEMA_VERSION,
            "generated_at": datetime.now().isoformat(),
            "model_used": config.TARGET_MODEL,
            "source_artifact": str(args.file),
            "summary": summary_content
        }

        helpers.save_json(final_output, paths["summary"])
        print(f"✨ Summary saved to: {paths['summary']}")
        update_manifest(title, helpers.get_safe_title(title), chapter_num, paths)

if __name__ == "__main__":
    main()