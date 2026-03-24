import os
from pathlib import Path
from core import config
from core.utils import file_io, network

def process_archive(title: str, chapter_str: str, url: str, lang: str = "en"):
    print(f"☁️ Initiating Cloud Import for '{title}' Ch {chapter_str}...")
    paths = file_io.get_paths(title, chapter_str)
    slug = file_io.get_safe_title(title)
    
    archive_dir = config.DATA_DIR / "raw_archives"
    extract_dir = config.DATA_DIR / "extracted_images" / slug / f"ch{chapter_str}"
    
    file_io.ensure_directory(archive_dir)
    file_io.cleanup_directory(extract_dir)
    zip_path = archive_dir / f"{slug}_ch{chapter_str}.zip"
    
    if "drive.google.com" in url:
        print("🔗 Source: Google Drive detected.")
        success = network.download_gdrive(url, str(zip_path))
    else:
        print("🔗 Source: Direct/Dropbox link detected.")
        success = network.download_direct_file(url, str(zip_path))
        
    if not success:
        print("❌ Failed to download the archive.")
        return False
        
    print("📦 Extracting images...")
    if not file_io.extract_archive(str(zip_path), str(extract_dir)): return False
    if os.path.exists(zip_path): os.remove(zip_path)
    
    metadata = {
        "manga_title": title,
        "manga_id": "local_archive",
        "target_chapter": float(chapter_str),
        "chapter_map": {chapter_str: {"lang": lang, "uuid": "local_import", "local_dir": str(extract_dir)}}
    }
    file_io.save_json(metadata, paths["metadata"])
    print(f"✅ Archive imported successfully to: {extract_dir}")
    return True