import os
from pathlib import Path

# Try to load dotenv, but don't crash if it's missing 
# (Since your key is in the system secrets anyway!)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# --- PROJECT ROOT ---
BASE_DIR = Path(__file__).resolve().parent.parent

# --- API SETTINGS (Pulled from System Secrets) ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
TARGET_MODEL = os.getenv("TARGET_MODEL", "gemini-2.5-flash")
SCHEMA_VERSION = "1.0"

# --- DIRECTORY MAPPING ---
DATA_DIR = BASE_DIR / "data"
METADATA_BASE = DATA_DIR / "metadata"
ARTIFACT_BASE = DATA_DIR / "artifacts"
SUMMARY_BASE = DATA_DIR / "summaries"

def get_safe_title(title: str) -> str:
    """The central logic for slugging manga titles."""
    return "".join([c for c in title if c.isalpha() or c.isspace()]).replace(" ", "_").lower()

def get_paths(title: str, chapter: str):
    """Generates all necessary file paths for a specific chapter."""
    slug = get_safe_title(title)
    
    # Ensure folders exist
    for folder in [METADATA_BASE / slug, ARTIFACT_BASE / slug, SUMMARY_BASE / slug]:
        folder.mkdir(parents=True, exist_ok=True)
        
    return {
        "metadata": METADATA_BASE / slug / f"ch{chapter}_metadata.json",
        "artifact": ARTIFACT_BASE / slug / f"ch{chapter}_artifact.json",
        "summary": SUMMARY_BASE / slug / f"ch{chapter}_summary.json",
        "manifest": SUMMARY_BASE / slug / "manifest.json"
    }