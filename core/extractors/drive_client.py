import os
import json
import logging
import time
import io
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseUpload

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("DriveClient")


class DriveClient:
    """Google Drive client for OCR text storage with exponential backoff."""

    def __init__(self):
        # Load service account credentials from file at project root
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        service_account_path = os.path.join(project_root, "service_account.json")

        if not os.path.exists(service_account_path):
            raise ValueError(
                f"❌ service_account.json not found at {service_account_path}. "
                "Download from Google Cloud Console and save to project root."
            )

        # Build authenticated service with Drive API scope
        self.credentials = Credentials.from_service_account_file(
            service_account_path,
            scopes=["https://www.googleapis.com/auth/drive"]
        )
        self.service = build("drive", "v3", credentials=self.credentials)

    def _exponential_backoff(self, func, max_retries: int = 5):
        """
        Retry with exponential backoff on rate limits (429) or permission errors (403).
        Delays: 1s, 2s, 4s, 8s, 16s between attempts.
        """
        for attempt in range(max_retries):
            try:
                return func()
            except HttpError as e:
                if e.resp.status in (429, 403):
                    wait_time = 2 ** attempt
                    logger.warning(
                        f"⚠️ API rate limit (HTTP {e.resp.status}). "
                        f"Retry {attempt + 1}/{max_retries} in {wait_time}s..."
                    )
                    time.sleep(wait_time)
                else:
                    raise

        raise Exception(f"❌ Failed after {max_retries} retries due to rate limiting")

    def upload_text(self, folder_id: str, file_name: str, text_content: str) -> str:
        """
        Upload text as a Google Drive file in specified folder.

        Args:
            folder_id: Google Drive folder ID where file will be stored
            file_name: Name for the file on Drive (e.g., "series_001_chapter_005.txt")
            text_content: Raw text to upload (OCR output)

        Returns:
            Google Drive file ID of newly created file
        """
        def _do_upload():
            file_metadata = {
                "name": file_name,
                "parents": [folder_id],
            }

            # Wrap text content in BytesIO for MediaIoBaseUpload
            file_bytes = io.BytesIO(text_content.encode("utf-8"))
            media = MediaIoBaseUpload(file_bytes, mimetype="text/plain", resumable=True)

            response = self.service.files().create(
                body=file_metadata,
                media_body=media,
                fields="id"
            ).execute()

            return response["id"]

        file_id = self._exponential_backoff(_do_upload)
        logger.info(f"📤 Uploaded '{file_name}' → Drive file_id: {file_id}")
        return file_id

    def download_text(self, drive_file_id: str) -> str:
        """
        Download text content from a Google Drive file.

        Args:
            drive_file_id: Google Drive file ID

        Returns:
            Text content of the file (UTF-8 decoded)
        """
        def _do_download():
            request = self.service.files().get_media(fileId=drive_file_id)
            content = request.execute()
            return content.decode("utf-8")

        text_content = self._exponential_backoff(_do_download)
        logger.info(f"📥 Downloaded from Drive file_id: {drive_file_id}")
        return text_content
