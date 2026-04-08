import shutil
import subprocess
import os
import uuid
import logging
import sys
import time
import threading
from pathlib import Path
from datetime import datetime, timezone
from sqlalchemy import select, update
from concurrent.futures import ThreadPoolExecutor, as_completed

from core import config
from core.extractors import cloud_drive
from core.utils import file_io
from database.models import Chapter, ChapterProcessing, SeriesSource

# -------------------------------------------------------------------------
# Logging Setup
# -------------------------------------------------------------------------
log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)

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
    def __init__(self, db_session, series, title, start_chapter=-1):
        self.db = db_session
        self.series = series
        self.title = title
        self.start_chapter = start_chapter

        self.slug = file_io.get_safe_title(title)
        self.extract_dir = config.DATA_DIR / "extracted_images" / self.slug
        self.extract_dir.mkdir(parents=True, exist_ok=True)

    def parse_skip_chapters(self, skip_input):
        """
        Parses a comma-separated string of chapters and ranges into a set of floats.
        Example: "20, 25-30, 31.5" -> {20.0, 25.0, 26.0, ..., 30.0, 31.5}
        """
        skip_set = set()
        if not skip_input:
            return skip_set
            
        targets = [t.strip() for t in str(skip_input).split(",") if t.strip()]
        
        for t in targets:
            if "-" in t:
                try:
                    start_str, end_str = t.split("-")
                    start, end = int(start_str), int(end_str)
                    if start <= end:
                        skip_set.update(float(x) for x in range(start, end + 1))
                except ValueError:
                    logger.warning(f"Ignored invalid skip range '{t}'")
            else:
                try:
                    skip_set.add(float(t))
                except ValueError:
                    logger.warning(f"Ignored invalid skip chapter '{t}'")
                    
        return skip_set

    def ingest(self, gdrive_url=None, manual_method=None, skip_input=""):
        """The Traffic Controller: Routes to Web or GDrive."""
        logger.info(f"Tier 1: Ingesting {self.title}...")

        if manual_method == "web_gallery-dl":
            return self.ingest_web()
        if manual_method == "google_drive":
            return self.ingest_google_drive(gdrive_url, skip_input)

        source = self.db.execute(
            select(SeriesSource).where(
                SeriesSource.series_id == self.series.id,
                SeriesSource.is_active == True
            ).order_by(SeriesSource.priority.asc())
        ).scalars().first()

        if source and source.url and "http" in source.url:
            logger.info("Auto-Detect: Active web source found. Routing to Web (gallery-dl)...")
            return self.ingest_web()
        
        return self.ingest_google_drive(gdrive_url, skip_input)

    def download_single_chapter(self, chapter, config_path, source_url, abort_event):
        """Worker function for multi-threaded gallery-dl sessions."""
        if abort_event.is_set():
            return f"Skipped Ch. {chapter.chapter_number} (Global Abort Active)"

        folder_name = file_io.get_chapter_folder_name(chapter.chapter_number)
        target_path = self.extract_dir / folder_name
        
        if target_path.exists() and any(target_path.iterdir()):
            return f"Skipping Ch. {chapter.chapter_number} (Files already present)."

        target_path.mkdir(parents=True, exist_ok=True)

        chapter_url = chapter.url
        filter_args = []
        
        if not chapter_url:
            chapter_url = source_url
            filter_args = ["--filter", f"chapter == {chapter.chapter_number}"]

        cmd = [
            "gallery-dl",
            "--abort", "3",
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
            encoding='utf-8',   
            errors='replace',    
            bufsize=1
        )

        fatal_error = False
        for line in process.stdout:
            if abort_event.is_set():
                process.terminate()
                return f"Aborted Ch. {chapter.chapter_number} mid-flight."

            clean_line = line.strip()
            if "error" in clean_line.lower() or "403" in clean_line.lower() or "429" in clean_line.lower():
                logger.error(f"Error on Ch. {chapter.chapter_number} - {clean_line}")
                
                if "403" in clean_line or "429" in clean_line:
                    logger.critical(f"FATAL BLOCK DETECTED on Ch. {chapter.chapter_number}. Flipping Kill Switch!")
                    fatal_error = True
                    abort_event.set()
                    process.terminate()
                    break

        process.wait()
        time.sleep(1) 

        if fatal_error or abort_event.is_set():
            return f"Ch. {chapter.chapter_number} failed due to Global Abort."

        if process.returncode in [0, 2]:
            return f"Chapter {chapter.chapter_number} verified."
        else:
            return f"Chapter {chapter.chapter_number} finished with code {process.returncode}"

    def ingest_web(self):
        """Multi-threaded Sniper Ingester with real-time status updates."""
        root_dir = Path(__file__).resolve().parent.parent.parent
        config_path = root_dir / "config" / "gallery-dl.conf"

        actual_start = self.start_chapter if self.start_chapter != -1 else 1

        targets = self.db.query(Chapter).filter(
            Chapter.series_id == self.series.id,
            Chapter.chapter_number >= actual_start
        ).order_by(Chapter.chapter_number.asc()).all()

        if not targets:
            logger.warning("No chapters found in database. Run a Scan first.")
            return False

        logger.info(f"Processing {len(targets)} chapters starting from Ch. {actual_start}")

        source = self.db.execute(
            select(SeriesSource).where(
                SeriesSource.series_id == self.series.id,
                SeriesSource.is_active == True
            ).order_by(SeriesSource.priority.asc())
        ).scalars().first()
        source_url = source.url if source else ""

        abort_event = threading.Event()

        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {
                executor.submit(self.download_single_chapter, ch, config_path, source_url, abort_event): ch 
                for ch in targets
            }

            for future in as_completed(futures):
                result = future.result()
                logger.info(result)
                
                # Robust status update: if verified or skipping, mark as extracted in DB
                if "verified" in result.lower() or "skipping" in result.lower():
                    ch = futures[future]
                    proc = self.db.query(ChapterProcessing).filter(ChapterProcessing.chapter_id == ch.id).first()
                    if not proc:
                        proc = ChapterProcessing(chapter_id=ch.id)
                        self.db.add(proc)
                    
                    proc.is_extracted = True
                    self.db.commit() 

        if abort_event.is_set():
            logger.critical("INGESTION HALTED: The pipeline was shut down early to protect your IP.")
            return False

        return True

    def ingest_google_drive(self, url, skip_input=""):
        """Downloads and unpacks a zip from Google Drive, assigning sequential IDs."""
        logger.info("Processing Google Drive path...")
        
        skip_set = self.parse_skip_chapters(skip_input)
        if skip_set:
            logger.info(f"Configured to skip chapters: {sorted(list(skip_set))}")
            
        try:
            series_base_dir = self.extract_dir
            base_extract_path = None

            if series_base_dir.exists():
                existing_folders = [
                    d for d in series_base_dir.iterdir() 
                    if d.is_dir() and any(c.isdigit() for c in d.name)
                ]
                if existing_folders:
                    logger.info(f"Found {len(existing_folders)} existing chapters.")
                elif url:
                    base_extract_path = cloud_drive.fetch_and_unpack(self.title, url)
            elif url:
                base_extract_path = cloud_drive.fetch_and_unpack(self.title, url)
            else:
                logger.error("No GDrive URL provided.")
                return False

            chapter_folders = cloud_drive.scan_for_chapter_folders(base_extract_path) if base_extract_path else []
        except Exception as e:
            logger.error(f"GDrive Ingest Failed: {e}")
            return False

        existing_nums = [n[0] for n in self.db.query(Chapter.chapter_number).filter(Chapter.series_id == self.series.id).all()]
        
        if self.start_chapter != -1:
            next_num = self.start_chapter
            logger.info(f"Override Active: Forcing sequence to start at Ch. {next_num}")
        else:
            next_num = max(existing_nums) + 1 if existing_nums else 1
            logger.info(f"Auto-Append: Starting at Ch. {next_num}")

        chapter_folders = sorted(chapter_folders, key=lambda x: x.name)

        for folder_path in chapter_folders:
            chapter_num = float(next_num)

            if chapter_num in skip_set:
                logger.info(f"Skipping Ch. {chapter_num} (Database stub created)")
                exists = self.db.query(Chapter).filter(Chapter.series_id == self.series.id, Chapter.chapter_number == chapter_num).first()
                if not exists:
                    new_ch = Chapter(series_id=self.series.id, chapter_number=chapter_num)
                    self.db.add(new_ch)
                    self.db.flush()
                    self.db.add(ChapterProcessing(chapter_id=new_ch.id, is_extracted=False, ocr_extracted=False, summary_complete=False))
                
                next_num += 1
                continue

            exists = self.db.query(Chapter).filter(Chapter.series_id == self.series.id, Chapter.chapter_number == chapter_num).first()
            if not exists:
                new_ch = Chapter(series_id=self.series.id, chapter_number=chapter_num)
                self.db.add(new_ch)
                self.db.flush()
                proc = ChapterProcessing(chapter_id=new_ch.id)
                self.db.add(proc)
            else:
                proc = self.db.query(ChapterProcessing).filter(ChapterProcessing.chapter_id == exists.id).first()

            folder_name = file_io.get_chapter_folder_name(chapter_num)
            target_path = self.extract_dir / folder_name
            
            if not target_path.exists() or not any(target_path.iterdir()):
                target_path.mkdir(parents=True, exist_ok=True)
                for file in folder_path.iterdir():
                    if file.is_file() and not file.name.startswith('.'):
                        dest_filename = file.name
                        if '.' not in dest_filename:
                            dest_filename = f"{dest_filename}.jpg"
                        shutil.move(str(file), str(target_path / dest_filename))
            
            # Flip extraction bit
            if proc:
                proc.is_extracted = True
                
            next_num += 1

        if base_extract_path and base_extract_path.exists():
            shutil.rmtree(base_extract_path)
            
        self.db.commit()
        return True

    def cleanup(self):
        """Removes local images and updates DB flags once processing is 100% complete."""
        total_ch = self.db.query(Chapter).filter(Chapter.series_id == self.series.id).count()
        completed_ch = self.db.query(ChapterProcessing).join(Chapter).filter(
            Chapter.series_id == self.series.id, ChapterProcessing.summary_complete == True
        ).count()

        if total_ch > 0 and completed_ch == total_ch:
            logger.info("Tier 4: All chapters processed. Cleaning up images...")
            if self.extract_dir.exists():
                shutil.rmtree(self.extract_dir)
                
                # Reflect that images are gone in the DB Status table
                chapter_ids_query = self.db.query(Chapter.id).filter(Chapter.series_id == self.series.id)
                self.db.execute(
                    update(ChapterProcessing)
                    .where(ChapterProcessing.chapter_id.in_(chapter_ids_query))
                    .values(is_extracted=False)
                )
                self.db.commit()
        else:
            logger.info(f"Tier 4: Cleanup deferred ({completed_ch}/{total_ch} complete).")