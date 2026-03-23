import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# --- PROJECT ROOT ---
BASE_DIR = Path(__file__).resolve().parent.parent

# --- API SETTINGS ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
TARGET_MODEL = os.getenv("TARGET_MODEL", "gemini-2.0-flash")
SCHEMA_VERSION = "1.0"

# --- DIRECTORY MAPPING ---
DATA_DIR = BASE_DIR / "data"
METADATA_BASE = DATA_DIR / "metadata"
ARTIFACT_BASE = DATA_DIR / "artifacts"
SUMMARY_BASE = DATA_DIR / "summaries"

# --- API CONSTANTS ---
MANGADEX_API_URL = "https://api.mangadex.org"
LANGUAGE_PRIORITY = ["en", "es-la", "es", "pt-br", "pt", "fr", "ja", "ko"]