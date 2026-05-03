import os
from pathlib import Path
from dotenv import load_dotenv

# --- INITIALIZE ENVIRONMENT ---
# This loads variables from a file named '.env' in your root directory
load_dotenv()

# --- BASE DIRECTORIES ---
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

# --- SUB-DIRECTORIES ---
TEMP_DIR = DATA_DIR / "temp"

# --- MANIFEST & LOGS ---
MANIFEST_PATH = DATA_DIR / "manifest.json"
USAGE_LOG_PATH = DATA_DIR / "usage_log.json"

# --- API URLS ---
MANGADEX_API_URL = "https://api.mangadex.org"
MANGADEX_BASE_URL = "https://mangadex.org"

# --- LANGUAGE & CONTENT SETTINGS ---
LANGUAGE_PRIORITY = ["en", "ko", "ja", "es", "es-la", "fr", "pt-br"]
CONTENT_RATING = ["safe", "suggestive", "erotica"]

# --- AI & HARDWARE SETTINGS ---
# We map the .env names to these config variables
GEMINI_PROJECT = os.getenv("GEMINI_PROJECT", "")
GEMINI_API_KEY = os.getenv("GOOGLE_API_KEY", "") 
USE_GPU = os.getenv("USE_GPU", "False").lower() == "true"
GEMINI_MAX_RPM = int(os.getenv("GEMINI_MAX_RPM", 8))

# --- DATABASE SETTINGS ---
DATABASE_URL = os.getenv("DATABASE_URL")

# --- MODEL SETTINGS ---
# TARGET_MODEL = "gemini-2.5-flash"
DEFAULT_MODEL = "gemini-3.1-flash-lite-preview"
SUPPORTED_MODELS = [
    "gemini-3.1-flash-lite-preview",
    "gemini-2.5-flash"
]

AVAILABLE_MODELS = ["gemini-3.1-flash-lite-preview", "gemini-2.5-flash"]


SCHEMA_VERSION = "2.1"

# --- SYSTEM SETTINGS ---
DAILY_TOKEN_LIMIT = 500000 
MAX_RETRIES = 3

# --- AUTO-INITIALIZE ---
# Ensures the folder structure exists before the pipeline starts
for folder in [TEMP_DIR]:
    folder.mkdir(parents=True, exist_ok=True)