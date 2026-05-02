import os
import sys
import time
import io
from pathlib import Path
from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from googleapiclient.errors import HttpError
from sqlalchemy.orm import sessionmaker

# Add project root to path so we can import from root modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from database.session import engine
from database.models import Series, Chapter, OCRResult

load_dotenv()

# DRIVE_ARCHIVE_FOLDER_ID = os.getenv("DRIVE_ARCHIVE_FOLDER_ID")
DRIVE_ARCHIVE_FOLDER_ID = "1Rj6vhjvYCGlm7JKLbptiaVqPbr3WnSbC"
SCOPES = ['https://www.googleapis.com/auth/drive.file']

# --- 1. Google Drive Authentication (OAuth 2.0) ---
def get_drive_service():
    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first time.
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)

    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)

        # Save the credentials for the next run
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    return build('drive', 'v3', credentials=creds)

# --- 2. Exponential Backoff Upload ---
def upload_with_backoff(service, file_metadata, media, max_retries=5):
    retries = 0
    backoff_time = 2  # Start with 2 seconds wait

    while retries < max_retries:
        try:
            file = service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id'
            ).execute()
            return file.get('id')
        except HttpError as error:
            # Check if it's a rate limit error (403 or 429)
            if error.resp.status in [403, 429]:
                print(f"Rate limited by Google Drive. Retrying in {backoff_time} seconds...")
                print(f"API Error ({error.resp.status}) - {error._get_reason()}. Retrying in {backoff_time}s...")
                time.sleep(backoff_time)
                retries += 1
                backoff_time *= 2  # Exponentially increase wait time
            else:
                raise error # Re-raise if it's a different HTTP error
    
    raise Exception("Max retries exceeded. Could not upload file.")

# --- 3. Folder Management ---
def get_or_create_series_folder(service, series_name, parent_folder_id):
    safe_series_name = series_name.replace("'", "\\'")
    query = f"name='{safe_series_name}' and '{parent_folder_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
    results = service.files().list(q=query, spaces='drive', fields='files(id, name)').execute()
    items = results.get('files', [])

    if items:
        return items[0]['id']
    else:
        folder_metadata = {
            'name': series_name,
            'mimeType': 'application/vnd.google-apps.folder',
            'parents': [parent_folder_id]
        }
        folder = service.files().create(body=folder_metadata, fields='id').execute()
        return folder.get('id')

# --- 4. Main Migration Logic ---
def migrate_data():
    service = get_drive_service()
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        # Join tables and filter ONLY chapters that haven't been migrated yet
        # LIMIT 5 added for a safe dry-run! Remove `.limit(5)` when ready to run the full payload.
        query = session.query(OCRResult, Chapter, Series).join(
            Chapter, OCRResult.chapter_id == Chapter.id
        ).join(
            Series, Chapter.series_id == Series.id
        ).filter(Chapter.drive_file_id == None)

        records_to_migrate = query.all()
        print(f"Found {len(records_to_migrate)} chapters to migrate in this batch.")

        series_folder_cache = {}

        for ocr, chapter, series in records_to_migrate:
            print(f"Migrating: {series.title} - Chapter {chapter.chapter_number}...")

            # 1. Get/Create Series Sub-folder
            if series.id not in series_folder_cache:
                folder_id = get_or_create_series_folder(service, series.title, DRIVE_ARCHIVE_FOLDER_ID)
                series_folder_cache[series.id] = folder_id
            
            parent_folder_id = series_folder_cache[series.id]

            # 2. Prepare text payload
            file_metadata = {
                'name': f"{chapter.chapter_number}.txt",
                'parents': [parent_folder_id]
            }
            media = MediaIoBaseUpload(io.BytesIO(ocr.raw_text.encode('utf-8')), mimetype='text/plain')

            # 3. Upload to Drive with Backoff
            drive_file_id = upload_with_backoff(service, file_metadata, media)

            # 4. Save ID to database immediately
            chapter.drive_file_id = drive_file_id
            session.commit()
            
            print(f"✅ Success! Drive File ID saved: {drive_file_id}")

        print("🎉 Batch migration completed successfully!")

    except Exception as e:
        print(f"❌ Migration halted due to error: {e}")
        session.rollback()
    finally:
        session.close()

if __name__ == '__main__':
    migrate_data()