import os
import requests
import logging
import gdown

logger = logging.getLogger(__name__)

def download_image(session: requests.Session, url: str, path: str, retries: int = 3) -> bool:
    for i in range(retries):
        try:
            res = session.get(url, timeout=15)
            if res.status_code == 200:
                with open(path, 'wb') as f: f.write(res.content)
                return True
        except Exception:
            if i == retries - 1: return False
    return False

def download_gdrive(url: str, output_path: str) -> bool:
    print(f"☁️ Downloading from Google Drive...")
    try:
        gdown.download(url=url, output=str(output_path), quiet=False, fuzzy=True)
        return os.path.exists(output_path)
    except Exception as e:
        logger.error(f"Google Drive download failed: {e}")
        return False

def download_direct_file(url: str, output_path: str) -> bool:
    print(f"☁️ Downloading direct file...")
    try:
        if "dropbox.com" in url and "dl=0" in url:
            url = url.replace("dl=0", "dl=1")
            
        res = requests.get(url, stream=True)
        res.raise_for_status()
        with open(output_path, 'wb') as f:
            for chunk in res.iter_content(chunk_size=8192):
                f.write(chunk)
        return True
    except Exception as e:
        logger.error(f"Direct download failed: {e}")
        return False