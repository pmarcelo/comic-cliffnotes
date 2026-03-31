import os
from pathlib import Path
from core import config
from core.utils import file_io, network

def process_archive(title: str, chapter_str: str, url: str, start_chapter: int = 1, lang: str = "en"):
    """
    Orchestrates the cloud-to-local import. 
    Matches the new 'Narrative-First' artifact structure.
    """
    slug = file_io.get_safe_title(title)
    archive_dir = config.DATA_DIR / "raw_archives"
    # Keeping the extraction path organized by slug
    extract_dir = config.DATA_DIR / "extracted_images" / slug / f"ch{chapter_str}"
    zip_path = archive_dir / f"{slug}_ch{chapter_str}.zip"

    # --- Skip Prep/Download if images are already there ---
    if extract_dir.exists() and any(extract_dir.iterdir()):
        print(f"📍 Images detected in {extract_dir}. Skipping download.")
    else:
        print(f"🧹 Preparing clean workspace for {title}...")
        file_io.ensure_directory(archive_dir)
        file_io.cleanup_directory(extract_dir)

        if not _fetch_from_gdrive(url, zip_path):
            return False

        if not _unpack_archive(zip_path, extract_dir):
            return False

    # 🚀 Pass parameters to the metadata registration
    _register_local_metadata(title, slug, chapter_str, extract_dir, lang, start_chapter)
    
    return True

def _fetch_from_gdrive(url: str, zip_path: Path) -> bool:
    print("🔗 Source: Google Drive.")
    return network.download_gdrive(url, str(zip_path))

def _unpack_archive(zip_path: Path, extract_dir: Path) -> bool:
    print("📦 Extracting images...")
    if not file_io.extract_archive(str(zip_path), str(extract_dir)):
        return False
    
    if os.path.exists(zip_path):
        os.remove(zip_path)
    return True

def _register_local_metadata(title: str, slug: str, chapter_str: str, extract_dir: Path, lang: str, start_chapter: int):
    """
    Loads existing metadata and appends NEW chapters using smart auto-incrementing.
    """
    metadata_path = config.ARTIFACTS_DIR / slug / "metadata.json"
    
    # 1. 🚀 LOAD OR INITIALIZE MANIFEST
    if metadata_path.exists():
        metadata = file_io.load_json(metadata_path)
        print(f"📂 Found existing manifest: {len(metadata.get('chapter_map', {}))} chapters tracked.")
    else:
        metadata = {
            "manga_title": title,
            "slug": slug,
            "chapter_map": {}
        }

    if chapter_str == "MASTER_BATCH":
        print("🔍 Scanning extracted files for NEW chapter IDs...")
        
        # 2. 🚀 SMART INCREMENTING LOGIC
        # If we have existing chapters, find the highest 'target_chapter' and start after it
        existing_chapters = [int(v["target_chapter"]) for v in metadata["chapter_map"].values() if "target_chapter" in v]
        
        if existing_chapters:
            next_num = max(existing_chapters) + 1
            print(f"📈 Existing chapters found. Auto-starting new batch at Chapter {next_num}.")
        else:
            next_num = start_chapter
            print(f"🆕 Fresh manifest. Starting at Chapter {next_num}.")

        # 3. 🚀 SCAN AND APPEND
        new_chapters = _scan_for_chapters(extract_dir, lang, next_num, metadata["chapter_map"])
        metadata["chapter_map"].update(new_chapters)
    
    else:
        # Fallback for single-chapter manual imports
        metadata["chapter_map"][chapter_str] = {
            "lang": lang, 
            "local_dir": str(extract_dir),
            "target_chapter": str(start_chapter),
            "ocr_completed": False,
            "ai_completed": False
        }

    file_io.save_json(metadata, metadata_path)

def _scan_for_chapters(base_dir: Path, lang: str, next_chapter_num: int, existing_map: dict):
    """
    Crawls folders and assigns narrative chapter numbers sequentially.
    """
    unsorted_new_map = {}
    valid_extensions = {'.jpg', '.jpeg', '.png', '.webp'}
    
    for root, dirs, files in os.walk(base_dir):
        if "__MACOSX" in root: continue

        image_files = [f for f in files if Path(f).suffix.lower() in valid_extensions]

        if image_files and not dirs:
            folder_path = Path(root)
            ch_id = folder_path.name 
            
            # Skip if Tachimanga folder ID is already in our ledger
            if ch_id in existing_map:
                continue
            
            unsorted_new_map[ch_id] = {
                "lang": lang,
                "local_dir": str(folder_path),
                "ocr_completed": False,
                "ai_completed": False,
                "image_count": len(image_files) 
            }
            
    # Sort folders numerically (Tachimanga's internal IDs) to maintain order
    sorted_keys = sorted(unsorted_new_map.keys(), key=lambda x: int(x) if str(x).isdigit() else x)
    
    new_chapter_map = {}
    current_num = next_chapter_num 
    
    for k in sorted_keys:
        data = unsorted_new_map[k]
        data["target_chapter"] = str(current_num) 
        new_chapter_map[k] = data
        
        print(f"  ✅ ADDED: {k} -> Narrative Chapter {current_num}")
        current_num += 1 
        
    return new_chapter_map