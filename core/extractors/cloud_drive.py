import os
from pathlib import Path
from core import config
from core.utils import file_io, network

def process_archive(title: str, chapter_str: str, url: str, start_chapter: int = 1, lang: str = "en"):
    """
    Orchestrates the cloud-to-local import. 
    Skips download/extract if images already exist for a MASTER_BATCH.
    """
    paths = file_io.get_paths(title, chapter_str)
    slug = file_io.get_safe_title(title)
    
    archive_dir = config.DATA_DIR / "raw_archives"
    extract_dir = config.DATA_DIR / "extracted_images" / slug / f"ch{chapter_str}"
    zip_path = archive_dir / f"{slug}_ch{chapter_str}.zip"

    # --- Skip Prep/Download if images are already there ---
    if extract_dir.exists() and any(extract_dir.iterdir()):
        print(f"📍 Images detected in {extract_dir}. Skipping cleanup and download.")
    else:
        print(f"🧹 Preparing clean workspace for {title}...")
        _prepare_workspace(archive_dir, extract_dir)

        if not _fetch_from_gdrive(url, zip_path):
            return False

        if not _unpack_archive(zip_path, extract_dir):
            return False

    # 🚀 Pass start_chapter down to the registration logic
    _register_local_metadata(title, chapter_str, extract_dir, paths, lang, start_chapter)
    
    return True

# --- Helper Methods ---

def _prepare_workspace(archive_dir: Path, extract_dir: Path):
    """Ensures the archive folder exists and wipes any old extraction data."""
    file_io.ensure_directory(archive_dir)
    file_io.cleanup_directory(extract_dir)

def _fetch_from_gdrive(url: str, zip_path: Path) -> bool:
    """Directly triggers the Google Drive download utility."""
    print("🔗 Source: Google Drive.")
    return network.download_gdrive(url, str(zip_path))

def _unpack_archive(zip_path: Path, extract_dir: Path) -> bool:
    """Extracts images and removes the original ZIP archive."""
    print("📦 Extracting images...")
    if not file_io.extract_archive(str(zip_path), str(extract_dir)):
        return False
    
    if os.path.exists(zip_path):
        os.remove(zip_path)
    return True

def _register_local_metadata(title: str, chapter_str: str, extract_dir: Path, paths: dict, lang: str, start_chapter: int):
    """
    Loads existing metadata if available, scans for NEW chapters, 
    and appends them to the manifest securely.
    """
    # 1. 🚀 LOAD EXISTING MANIFEST
    if os.path.exists(paths["metadata"]):
        metadata = file_io.load_json(paths["metadata"])
        print(f"📂 Loaded existing manifest with {len(metadata.get('chapter_map', {}))} chapters.")
    else:
        metadata = {
            "manga_title": title,
            "manga_id": "local_archive",
            "chapter_map": {}
        }

    if chapter_str == "MASTER_BATCH":
        print("🔍 Scanning extracted files for NEW chapter IDs...")
        existing_map = metadata.get("chapter_map", {})
        
        # 2. 🚀 SCAN AND FILTER
        new_chapters = _scan_for_chapters(extract_dir, lang, start_chapter, existing_map)
        
        # 3. 🚀 APPEND NEW DATA TO THE MASTER MAP
        metadata["chapter_map"].update(new_chapters)
        metadata["target_chapter"] = 0.0 
    else:
        metadata["target_chapter"] = float(chapter_str)
        metadata["chapter_map"][chapter_str] = {
            "lang": lang, 
            "uuid": "local_import", 
            "local_dir": str(extract_dir)
        }

    file_io.save_json(metadata, paths["metadata"])

def _scan_for_chapters(base_dir: Path, lang: str, start_chapter: int, existing_map: dict):
    """
    Recursively crawls nesting to find folders containing images.
    Ignores folders already in the existing_map to prevent overwrites.
    """
    unsorted_new_map = {}
    valid_extensions = {'.jpg', '.jpeg', '.png', '.webp'}
    
    for root, dirs, files in os.walk(base_dir):
        if "__MACOSX" in root:
            continue

        image_files = [f for f in files if f.isdigit() or Path(f).suffix.lower() in valid_extensions]

        if image_files and not dirs:
            folder_path = Path(root)
            ch_id = folder_path.name 
            
            # 🚀 MAGIC CHECK: If folder is already in the database, skip it!
            if ch_id in existing_map:
                continue
            
            unsorted_new_map[ch_id] = {
                "lang": lang,
                "uuid": f"local_{ch_id}",
                "local_dir": str(folder_path),
                "ocr_completed": False,
                "ai_completed": False,
                "image_count": len(image_files) 
            }
            
    # Numerically sort ONLY the brand new folders
    sorted_keys = sorted(unsorted_new_map.keys(), key=lambda x: int(x) if str(x).isdigit() else x)
    
    new_chapter_map = {}
    current_chapter = start_chapter 
    
    for k in sorted_keys:
        data = unsorted_new_map[k]
        data["target_chapter"] = str(current_chapter) 
        new_chapter_map[k] = data
        
        print(f"  ✅ ADDED Folder {k} -> Chapter {current_chapter} ({data['image_count']} pages)")
        current_chapter += 1 
        
    return new_chapter_map