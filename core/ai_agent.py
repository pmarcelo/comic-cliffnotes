import os
import argparse
from datetime import datetime
from google import genai
from google.genai import types
from core import config, helpers

client = genai.Client(api_key=config.GEMINI_API_KEY)

def get_nearest_context(paths, current_ch: float):
    manifest = helpers.load_json(paths["manifest"])
    if not manifest: return None, False

    past_chapters = sorted([c for c in manifest["chapters_summarized"] if c < current_ch], reverse=True)
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
    if float(chapter_num) not in manifest["chapters_summarized"]:
        manifest["chapters_summarized"].append(float(chapter_num))
        manifest["chapters_summarized"].sort()

    helpers.save_json(manifest, paths["manifest"])
    print(f"📄 Manifest updated: {paths['manifest']}")

def generate_summary(artifact_data: dict, context_memory: str = None, is_gap: bool = False):
    # [Your existing prompt generation block goes here - unchanged]
    pass

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-f", "--file", required=True)
    args = parser.parse_args()

    artifact = helpers.load_json(args.file)
    if not artifact: return

    title = artifact.get("manga_title", "unknown")
    chapter_num = artifact.get("chapter_number", "0")
    paths = helpers.get_paths(title, str(chapter_num))

    context, gap_detected = get_nearest_context(paths, float(chapter_num))
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