import os
import json
import argparse
from datetime import datetime
from google import genai
from google.genai import types
from core import config  # Central Single Source of Truth

# 1. AI Setup from Config
client = genai.Client(api_key=config.GEMINI_API_KEY)

def get_nearest_context(paths, current_ch: float):
    """
    Finds the most recent completed summary before the current chapter.
    Returns: (context_string, is_gap_detected)
    """
    manifest_path = paths["manifest"]
    if not manifest_path.exists():
        return None, False

    try:
        with open(manifest_path, 'r', encoding='utf-8') as f:
            manifest = json.load(f)
        
        # Get all completed chapters smaller than current, sorted descending
        past_chapters = sorted(
            [c for c in manifest["chapters_summarized"] if c < current_ch], 
            reverse=True
        )

        if not past_chapters:
            return None, False

        nearest_ch = past_chapters[0]
        # A gap exists if the nearest chapter isn't the immediate predecessor (e.g., 2.0 -> 4.0)
        is_gap = (current_ch - nearest_ch) > 1.1 

        prev_summary_path = paths["title_dir"] / f"ch{nearest_ch}_summary.json"
        
        if prev_summary_path.exists():
            with open(prev_summary_path, 'r', encoding='utf-8') as f:
                prev_data = json.load(f)
                content = prev_data.get("summary", {})
                
                # We only pass the most vital narrative "DNA"
                events = ", ".join(content.get("key_events", []))
                cliff = content.get("ending_cliffhanger", "N/A")
                
                context_str = f"PREVIOUSLY (Ch {nearest_ch}): {events}. LAST CLIFFHANGER: {cliff}"
                return context_str, is_gap

    except Exception as e:
        print(f"⚠️ Warning: Could not retrieve context memory: {e}")
    
    return None, False

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
    You are a professional Manga researcher. Summarize this raw OCR text from "{title}" Chapter {chapter}.
    {memory_header}{gap_warning}
    
    Translate to English, ignore OCR noise, and output JSON.
    Maintain continuity with characters and terminology from the context provided.

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

    if not os.path.exists(args.file): return

    with open(args.file, 'r', encoding='utf-8') as f:
        artifact = json.load(f)

    # Resolve paths
    title = artifact.get("manga_title", "unknown")
    chapter_num = artifact.get("chapter_number", "0")
    paths = config.get_paths(title, str(chapter_num))
    slug = config.get_safe_title(title)

    # --- NARRATIVE MEMORY STEP ---
    # Fetch the "Nearest Neighbor" context before summarizing
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

        with open(paths["summary"], "w", encoding="utf-8") as f:
            json.dump(final_output, f, indent=2, ensure_ascii=False)

        print(f"✨ Summary saved to: {paths['summary']}")
        update_manifest(title, slug, chapter_num, paths)

if __name__ == "__main__":
    main()