import shutil

from core import config
from core.extractors import cloud_drive
from core.utils import file_io
from database.models import Chapter, ChapterProcessing


class IngestManager:
    def __init__(self, db_session, series, title, start_chapter=1):
        self.db = db_session
        self.series = series
        self.title = title
        self.start_chapter = start_chapter

        self.slug = file_io.get_safe_title(title)
        self.extract_dir = config.DATA_DIR / "extracted_images" / self.slug

    def ingest(self, url):
        print("📥 Tier 1: Ingesting...")

        try:
            # --- 1. Pre-Flight Check (Smart Skip) ---
            series_base_dir = config.DATA_DIR / "extracted_images" / self.slug
            base_extract_path = None

            if series_base_dir.exists():
                existing_folders = [
                    d
                    for d in series_base_dir.iterdir()
                    if d.is_dir() and d.name.isdigit()
                ]
                if existing_folders:
                    print(
                        f"  ℹ️ Found {len(existing_folders)} existing chapter folders for {self.slug}."
                    )
                    print("  ⏩ Skipping download; verifying DB sync.")
                else:
                    base_extract_path = cloud_drive.fetch_and_unpack(self.title, url)
            else:
                base_extract_path = cloud_drive.fetch_and_unpack(self.title, url)

            # --- 2. Smart Scanner ---
            if base_extract_path:
                chapter_folders = cloud_drive.scan_for_chapter_folders(
                    base_extract_path
                )
            else:
                chapter_folders = []

        except Exception as e:
            print(f"❌ Ingest Failed during Download/Scan: {e}")
            return False

        # --- 3. Determine starting point ---
        existing_nums = [
            n[0]
            for n in self.db.query(Chapter.chapter_number)
            .filter(Chapter.series_id == self.series.id)
            .all()
        ]
        next_num = max(existing_nums) + 1 if existing_nums else self.start_chapter

        # --- 4. The "Librarian" Loop ---
        for folder_path in chapter_folders:
            exists = (
                self.db.query(Chapter)
                .filter(
                    Chapter.series_id == self.series.id,
                    Chapter.chapter_number == next_num,
                )
                .first()
            )

            if not exists:
                new_ch = Chapter(series_id=self.series.id, chapter_number=next_num)
                self.db.add(new_ch)
                self.db.flush()

                proc = ChapterProcessing(chapter_id=new_ch.id)
                self.db.add(proc)
                print(f"  ✅ DB Registered: Ch {next_num}")
            else:
                print(f"  ℹ️  Ch {next_num} already exists in DB. Checking files...")

            target_base = config.DATA_DIR / "extracted_images" / self.slug
            target_path = target_base / str(next_num)

            if not target_path.exists() or not any(target_path.iterdir()):
                target_path.mkdir(parents=True, exist_ok=True)
                for file in folder_path.iterdir():
                    if file.is_file():
                        shutil.move(str(file), str(target_path / file.name))
                print(f"  📂 Files Organized: {target_path}")

            next_num += 1

        # --- 5. Cleanup the 'sync_ingest' shell ---
        if base_extract_path and base_extract_path.exists():
            shutil.rmtree(base_extract_path)

        self.db.commit()
        return True

    def cleanup(self):
        """Cleanup image workspace if all DB processing flags are set."""
        total_ch = (
            self.db.query(Chapter).filter(Chapter.series_id == self.series.id).count()
        )
        completed_ch = (
            self.db.query(ChapterProcessing)
            .join(Chapter)
            .filter(Chapter.series_id == self.series.id)
            .filter(ChapterProcessing.summary_complete == True)
            .count()
        )

        if total_ch > 0 and completed_ch == total_ch:
            print("\n🧹 Tier 4: All chapters processed in DB. Cleaning up workspace...")
            if self.extract_dir.exists():
                shutil.rmtree(self.extract_dir)
                print(f"🗑️ Deleted image workspace: {self.extract_dir}")
        else:
            print(
                f"\n⏳ Tier 4: Cleanup deferred ({completed_ch}/{total_ch} complete)."
            )
