import os
import sys
import json
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy.orm import sessionmaker

# Add project root to path so we can import from root modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from database.session import engine
from database.models import Series, Chapter

load_dotenv()

def run_sync():
    mode = input("Type 'export' (to pull from Local) or 'import' (to push to Remote): ").strip().lower()

    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        if mode == 'export':
            # Grab all chapters that have a drive_file_id
            results = session.query(Chapter, Series).join(Series, Chapter.series_id == Series.id).filter(Chapter.drive_file_id != None).all()
            
            mapping = []
            for chap, series in results:
                mapping.append({
                    "series_title": series.title,
                    "chapter_number": chap.chapter_number,
                    "drive_file_id": chap.drive_file_id
                })
                
            with open("drive_mappings.json", "w") as f:
                json.dump(mapping, f, indent=4)
                
            print(f"✅ Exported {len(mapping)} records to drive_mappings.json.")
            print("Next step: Change your .env to your REMOTE database and run this script again in 'import' mode!")

        elif mode == 'import':
            if not os.path.exists("drive_mappings.json"):
                print("❌ Cannot find drive_mappings.json! Run 'export' first.")
                return
                
            with open("drive_mappings.json", "r") as f:
                mapping = json.load(f)
                
            updated = 0
            for item in mapping:
                # Find the matching chapter in the remote DB
                chap = session.query(Chapter).join(Series, Chapter.series_id == Series.id).filter(
                    Series.title == item["series_title"],
                    Chapter.chapter_number == item["chapter_number"]
                ).first()
                
                if chap:
                    chap.drive_file_id = item["drive_file_id"]
                    updated += 1
                else:
                    print(f"⚠️ Skipping: Could not find {item['series_title']} Chapter {item['chapter_number']} in remote DB.")
                    
            session.commit()
            print(f"🎉 Successfully imported {updated} Drive IDs to your remote database!")

        else:
            print("Invalid input. Please run again and type 'export' or 'import'.")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        session.rollback()
    finally:
        session.close()

if __name__ == '__main__':
    run_sync()