import os
import sys
import json
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy.orm import sessionmaker
from datetime import datetime

# Add project root to path so we can import from root modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from database.session import engine
from database.models import (
    User, Series, Chapter, SeriesSource, StoryArc, SeriesMetadata,
    ChapterProcessing, Summary, ProcessingQueue, BridgeCache, QueueStatus
)

load_dotenv()


def to_dict(obj, exclude_cols):
    """Convert SQLAlchemy model to dict, excluding specified columns and handling datetime serialization."""
    result = {}
    for col in obj.__table__.columns:
        if col.name not in exclude_cols:
            value = getattr(obj, col.name)
            # Handle datetime serialization
            if isinstance(value, datetime):
                result[col.name] = value.isoformat()
            # Handle enum serialization
            elif hasattr(value, 'value'):
                result[col.name] = value.value
            else:
                result[col.name] = value
    return result


def deserialize_enums(data, model):
    """Convert enum string values back to their enum types for the given model."""
    if model == ProcessingQueue and 'status' in data and isinstance(data['status'], str):
        data['status'] = QueueStatus(data['status'])
    return data


def run_migration():
    mode = input("Type 'export' (Local) or 'import' (Remote): ").strip().lower()
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        if mode == 'export':
            print("\n📦 Starting export of all tables...\n")

            payload = {}

            # =========================================================================
            # EXPORT PHASE - Parent tables first, then dependent tables
            # =========================================================================

            # 1. USERS - No dependencies
            print("📦 Exporting users...")
            users = session.query(User).all()
            payload['users'] = [to_dict(u, ['id']) for u in users]
            print(f"   ✅ {len(users)} users")

            # 2. SERIES - No dependencies
            print("📦 Exporting series...")
            series_list = session.query(Series).all()
            payload['series'] = [to_dict(s, ['id']) for s in series_list]
            print(f"   ✅ {len(series_list)} series")

            # 3. SERIES_SOURCES - Depends on Series
            print("📦 Exporting series_sources...")
            sources = session.query(SeriesSource).all()
            sources_data = []
            for src in sources:
                data = to_dict(src, ['id', 'series_id'])
                data['_series_title'] = src.series.title
                sources_data.append(data)
            payload['series_sources'] = sources_data
            print(f"   ✅ {len(sources)} series_sources")

            # 4. SERIES_METADATA - Depends on Series
            print("📦 Exporting series_metadata...")
            metadata = session.query(SeriesMetadata).all()
            metadata_data = []
            for meta in metadata:
                data = to_dict(meta, ['id', 'series_id'])
                data['_series_title'] = meta.series.title
                metadata_data.append(data)
            payload['series_metadata'] = metadata_data
            print(f"   ✅ {len(metadata)} series_metadata")

            # 5. STORY_ARCS - Depends on Series
            print("📦 Exporting story_arcs...")
            arcs = session.query(StoryArc).all()
            arcs_data = []
            for arc in arcs:
                data = to_dict(arc, ['id', 'series_id'])
                data['_series_title'] = arc.series.title
                arcs_data.append(data)
            payload['story_arcs'] = arcs_data
            print(f"   ✅ {len(arcs)} story_arcs")

            # 6. CHAPTERS - Depends on Series
            print("📦 Exporting chapters...")
            chapters = session.query(Chapter).all()
            chapters_data = []
            for chap in chapters:
                data = to_dict(chap, ['id', 'series_id'])
                data['_series_title'] = chap.series.title
                chapters_data.append(data)
            payload['chapters'] = chapters_data
            print(f"   ✅ {len(chapters)} chapters")

            # 7. CHAPTER_PROCESSING - Depends on Chapter
            print("📦 Exporting chapter_processing...")
            processing = session.query(ChapterProcessing).all()
            processing_data = []
            for proc in processing:
                data = to_dict(proc, ['id', 'chapter_id'])
                data['_series_title'] = proc.chapter.series.title
                data['_chapter_number'] = proc.chapter.chapter_number
                processing_data.append(data)
            payload['chapter_processing'] = processing_data
            print(f"   ✅ {len(processing)} chapter_processing")

            # 8. SUMMARIES - Depends on Chapter
            print("📦 Exporting summaries...")
            summaries = session.query(Summary).all()
            summaries_data = []
            for summary in summaries:
                data = to_dict(summary, ['id', 'chapter_id'])
                data['_series_title'] = summary.chapter.series.title
                data['_chapter_number'] = summary.chapter.chapter_number
                summaries_data.append(data)
            payload['summaries'] = summaries_data
            print(f"   ✅ {len(summaries)} summaries")

            # 9. BRIDGE_CACHE - Depends on Series
            print("📦 Exporting bridge_cache...")
            bridges = session.query(BridgeCache).all()
            bridges_data = []
            for bridge in bridges:
                data = to_dict(bridge, ['id', 'series_id'])
                data['_series_title'] = bridge.series.title
                bridges_data.append(data)
            payload['bridge_cache'] = bridges_data
            print(f"   ✅ {len(bridges)} bridge_cache")

            # 10. PROCESSING_QUEUE - Depends on Series
            print("📦 Exporting processing_queue...")
            queue = session.query(ProcessingQueue).all()
            queue_data = []
            for item in queue:
                data = to_dict(item, ['id', 'series_id'])
                data['_series_title'] = item.series.title
                queue_data.append(data)
            payload['processing_queue'] = queue_data
            print(f"   ✅ {len(queue)} processing_queue")

            # Write to file
            with open("full_migration.json", "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=4, default=str)

            print("\n✅ Export complete! Saved to full_migration.json\n")

        elif mode == 'import':
            if not os.path.exists("full_migration.json"):
                print("❌ Cannot find full_migration.json! Run 'export' first.")
                return

            with open("full_migration.json", "r", encoding="utf-8") as f:
                payload = json.load(f)

            print("\n🚀 Starting import to remote database...\n")

            # =========================================================================
            # IMPORT PHASE - Parent tables first, then dependent tables
            # =========================================================================

            # 1. USERS - No dependencies, no dedup check needed (unique email)
            print("🚀 Importing users...")
            imported = skipped = 0
            for item in payload.get('users', []):
                exists = session.query(User).filter_by(email=item['email']).first()
                if not exists:
                    session.add(User(**item))
                    imported += 1
                else:
                    skipped += 1
            session.commit()
            print(f"   ✅ Imported {imported}, Skipped {skipped}")

            # 2. SERIES - No dependencies
            print("🚀 Importing series...")
            imported = skipped = 0
            for item in payload.get('series', []):
                exists = session.query(Series).filter_by(title=item['title']).first()
                if not exists:
                    session.add(Series(**item))
                    imported += 1
                else:
                    skipped += 1
            session.commit()
            print(f"   ✅ Imported {imported}, Skipped {skipped}")

            # 3. SERIES_SOURCES - Depends on Series
            print("🚀 Importing series_sources...")
            imported = skipped = 0
            for item in payload.get('series_sources', []):
                series_title = item.pop('_series_title')
                series = session.query(Series).filter_by(title=series_title).first()
                if series:
                    exists = session.query(SeriesSource).filter(
                        SeriesSource.series_id == series.id,
                        SeriesSource.url == item['url']
                    ).first()
                    if not exists:
                        session.add(SeriesSource(**item, series_id=series.id))
                        imported += 1
                    else:
                        skipped += 1
            session.commit()
            print(f"   ✅ Imported {imported}, Skipped {skipped}")

            # 4. SERIES_METADATA - Depends on Series
            print("🚀 Importing series_metadata...")
            imported = skipped = 0
            for item in payload.get('series_metadata', []):
                series_title = item.pop('_series_title')
                series = session.query(Series).filter_by(title=series_title).first()
                if series:
                    exists = session.query(SeriesMetadata).filter_by(series_id=series.id).first()
                    if not exists:
                        session.add(SeriesMetadata(**item, series_id=series.id))
                        imported += 1
                    else:
                        skipped += 1
            session.commit()
            print(f"   ✅ Imported {imported}, Skipped {skipped}")

            # 5. STORY_ARCS - Depends on Series
            print("🚀 Importing story_arcs...")
            imported = skipped = 0
            for item in payload.get('story_arcs', []):
                series_title = item.pop('_series_title')
                series = session.query(Series).filter_by(title=series_title).first()
                if series:
                    exists = session.query(StoryArc).filter(
                        StoryArc.series_id == series.id,
                        StoryArc.arc_title == item['arc_title']
                    ).first()
                    if not exists:
                        session.add(StoryArc(**item, series_id=series.id))
                        imported += 1
                    else:
                        skipped += 1
            session.commit()
            print(f"   ✅ Imported {imported}, Skipped {skipped}")

            # 6. CHAPTERS - Depends on Series
            print("🚀 Importing chapters...")
            imported = skipped = 0
            for item in payload.get('chapters', []):
                series_title = item.pop('_series_title')
                series = session.query(Series).filter_by(title=series_title).first()
                if series:
                    exists = session.query(Chapter).filter(
                        Chapter.series_id == series.id,
                        Chapter.chapter_number == item['chapter_number']
                    ).first()
                    if not exists:
                        session.add(Chapter(**item, series_id=series.id))
                        imported += 1
                    else:
                        skipped += 1
            session.commit()
            print(f"   ✅ Imported {imported}, Skipped {skipped}")

            # 7. CHAPTER_PROCESSING - Depends on Chapter
            print("🚀 Importing chapter_processing...")
            imported = skipped = 0
            for item in payload.get('chapter_processing', []):
                series_title = item.pop('_series_title')
                chapter_number = item.pop('_chapter_number')
                chapter = session.query(Chapter).join(Series).filter(
                    Series.title == series_title,
                    Chapter.chapter_number == chapter_number
                ).first()
                if chapter:
                    exists = session.query(ChapterProcessing).filter_by(chapter_id=chapter.id).first()
                    if not exists:
                        session.add(ChapterProcessing(**item, chapter_id=chapter.id))
                        imported += 1
                    else:
                        skipped += 1
            session.commit()
            print(f"   ✅ Imported {imported}, Skipped {skipped}")

            # 8. SUMMARIES - Depends on Chapter
            print("🚀 Importing summaries...")
            imported = skipped = 0
            for item in payload.get('summaries', []):
                series_title = item.pop('_series_title')
                chapter_number = item.pop('_chapter_number')
                chapter = session.query(Chapter).join(Series).filter(
                    Series.title == series_title,
                    Chapter.chapter_number == chapter_number
                ).first()
                if chapter:
                    exists = session.query(Summary).filter_by(chapter_id=chapter.id).first()
                    if not exists:
                        session.add(Summary(**item, chapter_id=chapter.id))
                        imported += 1
                    else:
                        skipped += 1
            session.commit()
            print(f"   ✅ Imported {imported}, Skipped {skipped}")

            # 9. BRIDGE_CACHE - Depends on Series
            print("🚀 Importing bridge_cache...")
            imported = skipped = 0
            for item in payload.get('bridge_cache', []):
                series_title = item.pop('_series_title')
                series = session.query(Series).filter_by(title=series_title).first()
                if series:
                    exists = session.query(BridgeCache).filter(
                        BridgeCache.series_id == series.id,
                        BridgeCache.start_chapter == item['start_chapter'],
                        BridgeCache.end_chapter == item['end_chapter']
                    ).first()
                    if not exists:
                        session.add(BridgeCache(**item, series_id=series.id))
                        imported += 1
                    else:
                        skipped += 1
            session.commit()
            print(f"   ✅ Imported {imported}, Skipped {skipped}")

            # 10. PROCESSING_QUEUE - Depends on Series
            print("🚀 Importing processing_queue...")
            imported = skipped = 0
            for item in payload.get('processing_queue', []):
                series_title = item.pop('_series_title')
                series = session.query(Series).filter_by(title=series_title).first()
                if series:
                    # Dedup by series_id + action to avoid duplicate queue items
                    exists = session.query(ProcessingQueue).filter(
                        ProcessingQueue.series_id == series.id,
                        ProcessingQueue.action == item['action']
                    ).first()
                    if not exists:
                        # Deserialize enum values
                        item = deserialize_enums(item, ProcessingQueue)
                        session.add(ProcessingQueue(**item, series_id=series.id))
                        imported += 1
                    else:
                        skipped += 1
            session.commit()
            print(f"   ✅ Imported {imported}, Skipped {skipped}")

            print("\n🎉 Full database migration complete!\n")

        else:
            print("❌ Invalid input. Please run again and type 'export' or 'import'.")

    except Exception as e:
        print(f"❌ Error: {e}")
        session.rollback()
        import traceback
        traceback.print_exc()
    finally:
        session.close()


if __name__ == '__main__':
    run_migration()
