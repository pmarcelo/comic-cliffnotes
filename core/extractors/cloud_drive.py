import os
from pathlib import Path
from core import config
from core.utils import file_io, network

def process_archive(title: str, chapter_str: str, url: str, lang: str = "en"):
    """
    Orchestrates the cloud-to-local import. 
    Skips download/extract if images already exist for a MASTER_BATCH.
    """
    paths = file_io.get_paths(title, chapter_str)
    slug = file_io.get_safe_title(title)
    
    archive_dir = config.DATA_DIR / "raw_archives"
    # Note: We look one level deeper for the MASTER_BATCH folder
    extract_dir = config.DATA_DIR / "extracted_images" / slug / f"ch{chapter_str}"
    zip_path = archive_dir / f"{slug}_ch{chapter_str}.zip"

    # --- THE FIX: Skip Prep/Download if images are already there ---
    if extract_dir.exists() and any(extract_dir.iterdir()):
        print(f"📍 Images detected in {extract_dir}. Skipping cleanup and download.")
    else:
        print(f"🧹 Preparing clean workspace for {title}...")
        _prepare_workspace(archive_dir, extract_dir)

        if not _fetch_from_gdrive(url, zip_path):
            return False

        if not _unpack_archive(zip_path, extract_dir):
            return False

    # This will now run the scan on the existing (or newly downloaded) images
    _register_local_metadata(title, chapter_str, extract_dir, paths, lang)
    
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

def _register_local_metadata(title: str, chapter_str: str, extract_dir: Path, paths: dict, lang: str):
    """
    Creates the JSON metadata. If chapter_str is 'MASTER_BATCH', 
    it scans subfolders to build a bulk mapping.
    """
    metadata = {
        "manga_title": title,
        "manga_id": "local_archive",
        "chapter_map": {}
    }

    if chapter_str == "MASTER_BATCH":
        # New Logic: Scan the entire extraction for chapter folders
        print("🔍 Scanning extracted files for chapter IDs...")
        metadata["chapter_map"] = _scan_for_chapters(extract_dir, lang)
        metadata["target_chapter"] = 0.0 # Placeholder for batch
    else:
        # Standard single-chapter logic
        metadata["target_chapter"] = float(chapter_str)
        metadata["chapter_map"] = {
            chapter_str: {
                "lang": lang, 
                "uuid": "local_import", 
                "local_dir": str(extract_dir)
            }
        }

    file_io.save_json(metadata, paths["metadata"])

def _scan_for_chapters(base_dir: Path, lang: str):
    """
    Recursively crawls deep nesting to find folders containing images.
    Handles 'naked' files (no extensions) and standard image formats.
    """
    chapter_map = {}
    valid_extensions = {'.jpg', '.jpeg', '.png', '.webp'}
    
    print(f"🔍 Deep scanning for chapters in: {base_dir}")
    
    for root, dirs, files in os.walk(base_dir):
        # 1. Skip system/junk folders (like __MACOSX)
        if "__MACOSX" in root:
            continue

        # 2. Identify 'images' based on:
        #    - Filename is a digit (e.g., '0', '1', '10')
        #    - OR filename has a common image extension
        image_files = [
            f for f in files 
            if f.isdigit() or Path(f).suffix.lower() in valid_extensions
        ]

        # 3. If a folder has images and NO subdirectories, it's a chapter leaf
        if image_files and not dirs:
            folder_path = Path(root)
            ch_id = folder_path.name # The '63730' anchor
            
            chapter_map[ch_id] = {
                "lang": lang,
                "uuid": f"local_{ch_id}",
                "local_dir": str(folder_path),
                "ocr_completed": False,
                "ai_completed": False,
                "image_count": len(image_files) # Store count for the final report
            }
            print(f"  ✅ Found Chapter: {ch_id} ({len(image_files)} pages)")
            
    return chapter_map