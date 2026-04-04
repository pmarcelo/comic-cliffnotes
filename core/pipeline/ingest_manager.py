import shutil
import subprocess
import os
import uuid
from pathlib import Path
from sqlalchemy import select

from core import config
from core.extractors import cloud_drive
from core.utils import file_io
from database.models import Chapter, ChapterProcessing, SeriesSource


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
        If manual_method is provided (from UI), it respects that.
        Otherwise, it auto-detects based on available database sources.
        """
        print("📥 Tier 1: Ingesting...")

        # 1. Explicit Manual Overrides
        if manual_method == "web_gallery-dl":
            return self.ingest_web()
        if manual_method == "google_drive":
            return self.ingest_google_drive(gdrive_url)

        # 2. AUTO-DETECTION LOGIC
        # Look for an active web source in the database for this series
        source = self.db.execute(
            select(SeriesSource).where(
                SeriesSource.series_id == self.series.id,
                SeriesSource.is_active == True
            ).order_by(SeriesSource.priority.asc())
        ).scalars().first()

        if source and source.url and "http" in source.url:
            print(f"🤖 Auto-Detect: Active web source found. Routing to Web (gallery-dl)...")
            return self.ingest_web()
        
        # 3. FALLBACK
        # If no web source is found, route to GDrive logic.
        # Note: If gdrive_url is None, the GDrive logic will still run its 
        # 'Pre-flight check' to see if images are already present locally.
        print(f"☁️ Auto-Detect: No web source found. Routing to Google Drive logic...")
        return self.ingest_google_drive(gdrive_url)

    def ingest_google_drive(self, url):
        """
        Downloads and unpacks a zip from Google Drive, then moves folders 
        into the structured directory and syncs with the database.
        """
        print("☁️ Processing Google Drive path...")

        try:
            series_base_dir = self.extract_dir
            base_extract_path = None

            # Pre-flight check: If folders exist, we skip the heavy download
            if series_base_dir.exists():
                existing_folders = [
                    d for d in series_base_dir.iterdir() 
                    if d.is_dir() and any(c.isdigit() for c in d.name)
                ]
                if existing_folders:
                    print(f"  ℹ️ Found {len(existing_folders)} existing chapter folders for {self.slug}.")
                    print("  ⏩ Skipping download; verifying DB sync.")
                elif url:
                    base_extract_path = cloud_drive.fetch_and_unpack(self.title, url)
            elif url:
                base_extract_path = cloud_drive.fetch_and_unpack(self.title, url)
            else:
                print("⚠️ No GDrive URL provided and no local folders found.")
                return False

            # Scan the unpacked data for chapter-like folders
            chapter_folders = cloud_drive.scan_for_chapter_folders(base_extract_path) if base_extract_path else []

        except Exception as e:
            print(f"❌ GDrive Ingest Failed: {e}")
            return False

        # Determine starting point for numbering
        existing_nums = [
            n[0] for n in self.db.query(Chapter.chapter_number)
            .filter(Chapter.series_id == self.series.id).all()
        ]
        next_num = max(existing_nums) + 1 if existing_nums else self.start_chapter

        # Move folders and create DB records
        for folder_path in chapter_folders:
            exists = self.db.query(Chapter).filter(
                Chapter.series_id == self.series.id,
                Chapter.chapter_number == next_num,
            ).first()

            if not exists:
                new_ch = Chapter(series_id=self.series.id, chapter_number=next_num)
                self.db.add(new_ch)
                self.db.flush()

                proc = ChapterProcessing(chapter_id=new_ch.id)
                self.db.add(proc)

            folder_name = file_io.get_chapter_folder_name(next_num)
            target_path = self.extract_dir / folder_name

            if not target_path.exists() or not any(target_path.iterdir()):
                target_path.mkdir(parents=True, exist_ok=True)
                for file in folder_path.iterdir():
                    if file.is_file():
                        shutil.move(str(file), str(target_path / file.name))

            next_num += 1

        if base_extract_path and base_extract_path.exists():
            shutil.rmtree(base_extract_path)

        self.db.commit()
        return True

    def ingest_web(self):
        """
        Uses gallery-dl to download images for chapters that have placeholders 
        in the DB but no local images yet.
        """
        print("🌐 Processing Web (gallery-dl) path...")

        source = self.db.execute(
            select(SeriesSource).where(
                SeriesSource.series_id == self.series.id,
                SeriesSource.is_active == True
            ).order_by(SeriesSource.priority.asc())
        ).scalars().first()

        if not source:
            print(f"❌ Aborting: No active web source configured for '{self.title}'.")
            return False

        targets = self.db.query(Chapter).filter(
            Chapter.series_id == self.series.id,
            Chapter.chapter_number >= self.start_chapter
        ).order_by(Chapter.chapter_number.asc()).all()

        if not targets:
            print("ℹ️ No chapter placeholders found in DB. Run a 'Scan' first.")
            return False

        for chapter in targets:
            folder_name = file_io.get_chapter_folder_name(chapter.chapter_number)
            target_path = self.extract_dir / folder_name
            
            if target_path.exists() and any(target_path.iterdir()):
                print(f"  ✅ Chapter {chapter.chapter_number} already exists locally.")
                continue

            print(f"🚀 Downloading Chapter {chapter.chapter_number} via gallery-dl...")
            
            cmd = [
                "gallery-dl",
                "-D", str(self.extract_dir),
                "-f", f"{folder_name}/{{num:03d}}.{{extension}}",
                "--no-directory",
                "--filter", f"chapter == {chapter.chapter_number}",
                source.url
            ]

            try:
                subprocess.run(cmd, check=True, capture_output=True, timeout=300)
            except subprocess.CalledProcessError as e:
                print(f"⚠️ gallery-dl failed for chapter {chapter.chapter_number}: {e.stderr}")
            except subprocess.TimeoutExpired:
                print(f"⏱️ Timeout reached for chapter {chapter.chapter_number}.")

        return True

    def cleanup(self):
        """
        Removes the local image workspace only if every chapter 
        in the DB for this series has a completed AI summary.
        """
        total_ch = self.db.query(Chapter).filter(Chapter.series_id == self.series.id).count()
        completed_ch = (
            self.db.query(ChapterProcessing)
            .join(Chapter)
            .filter(Chapter.series_id == self.series.id)
            .filter(ChapterProcessing.summary_complete == True)
            .count()
        )

        if total_ch > 0 and completed_ch == total_ch:
            print("\n🧹 Tier 4: All chapters processed. Cleaning up image workspace...")
            if self.extract_dir.exists():
                shutil.rmtree(self.extract_dir)
                print(f"🗑️ Deleted: {self.extract_dir}")
        else:
            print(f"\n⏳ Tier 4: Cleanup deferred ({completed_ch}/{total_ch} complete).")