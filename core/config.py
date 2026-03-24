import os
from pathlib import Path

# --- BASE DIRECTORIES ---
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

# --- SUB-DIRECTORIES ---
TEMP_DIR = DATA_DIR / "temp"
ARTIFACTS_DIR = DATA_DIR / "artifacts"
SUMMARIES_DIR = DATA_DIR / "summaries"
RAW_ARCHIVES_DIR = DATA_DIR / "raw_archives"

# --- MANIFEST & LOGS ---
MANIFEST_PATH = DATA_DIR / "manifest.json"
USAGE_LOG_PATH = DATA_DIR / "usage_log.json"

# --- API URLS ---
MANGADEX_API_URL = "https://api.mangadex.org"
MANGADEX_BASE_URL = "https://mangadex.org"

# --- LANGUAGE & CONTENT SETTINGS ---
# RE-ENABLED MULTI-LANGUAGE SUPPORT
# Priority is given in this order (English first, then Korean, then Others)
LANGUAGE_PRIORITY = ["en", "ko", "ja", "es", "es-la", "fr", "pt-br"]
CONTENT_RATING = ["safe", "suggestive", "erotica"]

# --- AI SETTINGS ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "YOUR_KEY_HERE")
TARGET_MODEL = "gemini-2.0-flash"
SCHEMA_VERSION = "2.1"

# --- SYSTEM SETTINGS ---
DAILY_TOKEN_LIMIT = 500000 
MAX_RETRIES = 3

# --- AUTO-INITIALIZE ---
for folder in [TEMP_DIR, ARTIFACTS_DIR, SUMMARIES_DIR, RAW_ARCHIVES_DIR]:
    folder.mkdir(parents=True, exist_ok=True)