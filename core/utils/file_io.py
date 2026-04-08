import json
import os
import shutil
import zipfile
from pathlib import Path
from core import config

def get_safe_title(title):
    """Turns a title into a filesystem-friendly slug."""
    if title is None or not str(title).strip() or str(title).lower() == "none":
        return "unknown_manga"
    title_str = str(title)
    # Keep only alphanumeric and spaces, then swap spaces for underscores
    return "".join([c for c in title_str if c.isalnum() or c.isspace()]).replace(" ", "_").lower()

def get_chapter_folder_name(chapter_number: float) -> str:
    """
    Normalizes chapter numbers for filesystem paths.
    130.0 -> "130"
    101.5 -> "101.5"
    """
    if chapter_number is None:
        return "0"
        
    # If it's a whole number, strip the .0 by casting to int
    if float(chapter_number).is_integer():
        return str(int(chapter_number))
    
    # Otherwise, keep the decimal (e.g., "101.5")
    return str(chapter_number)

def get_paths(title, chapter_str):
    """Generates a dictionary of paths for a specific chapter."""
    slug = get_safe_title(title)
    ch_slug = f"ch_{chapter_str}"
    
    manga_dir = config.ARTIFACTS_DIR / slug
    chapter_dir = manga_dir / ch_slug
    summary_dir = config.SUMMARIES_DIR / slug
    
    # Ensure directories exist
    chapter_dir.mkdir(parents=True, exist_ok=True)
    summary_dir.mkdir(parents=True, exist_ok=True)

    return {
        "metadata": manga_dir / "metadata.json",
        "raw_text": chapter_dir / "raw_ocr.txt",
        "summary": summary_dir / f"chapter_{chapter_str}.json"
    }

def ensure_directory(directory_path):
    """Ensures a directory exists. Creates it if it doesn't."""
    path = Path(directory_path)
    path.mkdir(parents=True, exist_ok=True)

def cleanup_directory(directory_path):
    """Deletes all contents of a directory or creates it if missing."""
    path = Path(directory_path)
    if path.exists() and path.is_dir():
        for item in path.iterdir():
            if item.is_file() or item.is_symlink(): 
                item.unlink()
            elif item.is_dir(): 
                shutil.rmtree(item)
    else:
        path.mkdir(parents=True, exist_ok=True)

def save_json(data, path):
    """Saves a dictionary to a JSON file."""
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def load_json(path):
    """Loads a JSON file into a dictionary."""
    if not os.path.exists(path): 
        return None
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def extract_archive(zip_path, extract_dir):
    """Unzips an archive to a target directory."""
    try:
        print(f"Extracting {zip_path} to {extract_dir}...")
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_dir)
        return True
    except Exception as e:
        print(f"Extraction error: {e}")
        return False

def update_chapter_metadata(metadata_path, original_id, ai_data):
    """Legacy helper for JSON-based metadata management."""
    data = load_json(metadata_path)
    if not data: return
    if original_id in data.get("chapter_map", {}):
        data["chapter_map"][original_id]["ai_chapter_num"] = ai_data.get("identified_chapter_num")
        data["chapter_map"][original_id]["ai_title"] = ai_data.get("identified_title")
        data["chapter_map"][original_id]["processed"] = True
        save_json(data, metadata_path)