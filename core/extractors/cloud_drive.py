import os
from pathlib import Path
from core import config
from core.utils import file_io, network

def process_archive(title: str, chapter_str: str, url: str, lang: str = "en"):
    """
    Orchestrates the cloud-to-local import pipeline by downloading, 
    extracting, and registering chapter images.
    """
    print(f"☁️ Initiating Cloud Import for '{title}' Ch {chapter_str}...")
    
    # 1. Path Generation: Define where the ZIP goes and where images are extracted
    paths = file_io.get_paths(title, chapter_str)
    slug = file_io.get_safe_title(title)
    
    archive_dir = config.DATA_DIR / "raw_archives"
    extract_dir = config.DATA_DIR / "extracted_images" / slug / f"ch{chapter_str}"
    zip_path = archive_dir / f"{slug}_ch{chapter_str}.zip"

    # 2. Workspace Setup: Prepare directories for clean download/extraction
    _prepare_workspace(archive_dir, extract_dir)

    # 3. Fetch: Download archive from Google Drive
    if not _fetch_from_gdrive(url, zip_path):
        return False

    # 4. Unpack: Extract files and delete the ZIP to save space
    if not _unpack_archive(zip_path, extract_dir):
        return False

    # 5. Register: Save metadata so the OCR engine can locate the local images
    _register_local_metadata(title, chapter_str, extract_dir, paths, lang)
    
    print(f"✅ Archive imported successfully to: {extract_dir}")
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
    """Creates the 'Bridge' metadata JSON used by the OCR engine."""
    metadata = {
        "manga_title": title,
        "manga_id": "local_archive",
        "target_chapter": float(chapter_str),
        "chapter_map": {
            chapter_str: {
                "lang": lang, 
                "uuid": "local_import", 
                "local_dir": str(extract_dir)
            }
        }
    }
    # Important: Matches (data, path) argument order
    file_io.save_json(metadata, paths["metadata"])