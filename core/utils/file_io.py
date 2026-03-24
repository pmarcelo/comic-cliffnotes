import json
import os
import shutil
from pathlib import Path
from core import config

def get_safe_title(title):
    """Turns a title into a filesystem-friendly slug."""
    if title is None or not str(title).strip() or str(title).lower() == "none":
        return "unknown_manga"
    title_str = str(title)
    return "".join([c for c in title_str if c.isalpha() or c.isspace()]).replace(" ", "_").lower()

def get_paths(title, chapter_str):
    """Generates a dictionary of paths. Matches run_pipeline expectations."""
    slug = get_safe_title(title)
    ch_slug = f"ch_{chapter_str}"
    
    manga_dir = config.ARTIFACTS_DIR / slug
    chapter_dir = manga_dir / ch_slug
    
    chapter_dir.mkdir(parents=True, exist_ok=True)
    config.SUMMARIES_DIR.mkdir(parents=True, exist_ok=True)

    return {
        "metadata": manga_dir / "metadata.json",
        "raw_text": chapter_dir / "raw_ocr.txt",
        # CHANGED: 'processed_json' -> 'summary' to fix the KeyError
        "summary": config.SUMMARIES_DIR / f"{slug}_{ch_slug}.json"
    }

def update_chapter_metadata(metadata_path, original_id, ai_data):
    """Saves the AI-identified chapter number back to the master metadata."""
    data = load_json(metadata_path)
    if not data: return
    if original_id in data["chapter_map"]:
        data["chapter_map"][original_id]["ai_chapter_num"] = ai_data.get("identified_chapter_num")
        data["chapter_map"][original_id]["ai_title"] = ai_data.get("identified_title")
        data["chapter_map"][original_id]["processed"] = True
        save_json(metadata_path, data)

def cleanup_directory(directory_path):
    path = Path(directory_path)
    if path.exists() and path.is_dir():
        for item in path.iterdir():
            if item.is_file() or item.is_symlink(): item.unlink()
            elif item.is_dir(): shutil.rmtree(item)
    else:
        path.mkdir(parents=True, exist_ok=True)

def save_json(path, data):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def load_json(path):
    if not os.path.exists(path): return None
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)