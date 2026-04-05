import shutil
import subprocess
import os
import uuid
import logging
import sys # Added for console encoding fix
from pathlib import Path
from datetime import datetime, timezone
from sqlalchemy import select

from core import config
from core.extractors import cloud_drive
from core.utils import file_io
from database.models import Chapter, ChapterProcessing, SeriesSource

# -------------------------------------------------------------------------
# Logging Setup (Fixed for UTF-8)
# -------------------------------------------------------------------------
log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)

# We define the handlers explicitly to ensure UTF-8 encoding
file_handler = logging.FileHandler(log_dir / "ingest.log", encoding='utf-8')
stream_handler = logging.StreamHandler(sys.stdout)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[file_handler, stream_handler]
)
logger = logging.getLogger(__name__)

# -------------------------------------------------------------------------
# Ingest Manager
# -------------------------------------------------------------------------

class IngestManager:
    def __init__(self, db_session, series, title, start_chapter=1):
        self.db = db_session
        self.series = series
        self.title = title
        self.start_chapter = start_chapter

        self.slug = file_io.get_safe_title(title)
        self.extract_dir = config.DATA_DIR / "extracted_images" / self.slug

    def ingest(self, gdrive_url=None, manual_method=None):
        """
        The Traffic Controller: Determines the best ingestion path.
        """
        logger.info(f"📥 Tier 1: Ingesting {self.title}...")

        # 1. Explicit Manual Overrides
        if manual_method == "web_gallery-dl":
            return self.ingest_web()
        if manual_method == "google_drive":
            return self.ingest_google_drive(gdrive_url)

        # 2. AUTO-DETECTION LOGIC
        source = self.db.execute(
            select(SeriesSource).where(
                SeriesSource.series_id == self.series.id,
                SeriesSource.is_active == True
            ).order_by(SeriesSource.priority.asc())
        ).scalars().first()

        if source and source.url and "http" in source.url:
            logger.info("🤖 Auto-Detect: Active web source found. Routing to Web (gallery-dl)...")
            return self.ingest_web()
        
        # 3. FALLBACK
        logger.info("☁️ Auto-Detect: No web source found. Routing to Google Drive logic...")
        return self.ingest_google_drive(gdrive_url)

    def ingest_web(self):
        """
        High-efficiency batch ingester using gallery-dl.
        Uses direct chapter URLs to skip metadata redundancy and streams logs in real-time.
        """
        root_dir = Path(__file__).resolve().parent.parent.parent
        config_path = root_dir / "config" / "gallery-dl.conf"

        # 1. Fetch Source
        source = self.db.execute(
            select(SeriesSource).where(
                SeriesSource.series_id == self.series.id,
                SeriesSource.is_active == True
            ).order_by(SeriesSource.priority.asc())
        ).scalars().first()

        if not source:
            logger.error(f"❌ Aborting: No active web source configured for '{self.title}'.")
            return False

        # 2. Identify Target Chapters
        targets = self.db.query(Chapter).filter(
            Chapter.series_id == self.series.id,
            Chapter.chapter_number >= self.start_chapter
        ).order_by(Chapter.chapter_number.asc()).all()

        if not targets:
            logger.warning("ℹ️ No chapters found in database. Run a 'Scan' first.")
            return False

        logger.info(f"📑 Processing {len(targets)} chapters starting from Ch. {self.start_chapter}")

        # 3. Download Loop
        for chapter in targets:
            folder_name = file_io.get_chapter_folder_name(chapter.chapter_number)
            target_path = self.extract_dir / folder_name
            
            # --- IDEMPOTENCY CHECK ---
            if target_path.exists() and any(target_path.iterdir()):
                logger.info(f"⏭️  Skipping Ch. {chapter.chapter_number} (Files already present).")
                continue

            # --- URL RESOLUTION (Sniper Mode) ---
            chapter_url = chapter.url
            filter_args = []
            
            if not chapter_url:
                logger.warning(f"🔍 No direct URL for Ch. {chapter.chapter_number}. Falling back to series search.")
                chapter_url = source.url
                filter_args = ["--filter", f"chapter == {chapter.chapter_number}"]

            logger.info(f"🚀 Downloading Chapter {chapter.chapter_number}...")

            # --- EXECUTION ---
            cmd = [
                "gallery-dl",
                "-c", str(config_path),
                "-D", str(target_path),
                "-o", "extractor.directory=[]",
                "-f", "{page:03d}.{extension}",
                *filter_args,
                chapter_url
            ]

            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding='utf-8',  # 🎯 FIX: Force UTF-8 for the process output
                errors='replace',   # 🎯 FIX: Replace unreadable chars instead of crashing
                bufsize=1
            )

            # Stream real-time feedback
            try:
                for line in process.stdout:
                    clean_line = line.strip()
                    if "downloading" in clean_line.lower() or "jpg" in clean_line.lower():
                        print(f"  📥 {clean_line}")
                    elif "error" in clean_line.lower() or "403" in clean_line.lower():
                        logger.error(f"  ❌ {clean_line}")
            except UnicodeDecodeError:
                # Extra safety for the iterator itself
                pass

            process.wait()

            if process.returncode == 0:
                logger.info(f"✅ Chapter {chapter.chapter_number} Complete.")
            else:
                logger.warning(f"⚠️ Chapter {chapter.chapter_number} exited with code {process.returncode}")

        return True

    def ingest_google_drive(self, url):
        # ... (Same as before)
        pass

    def cleanup(self):
        # ... (Same as before)
        pass