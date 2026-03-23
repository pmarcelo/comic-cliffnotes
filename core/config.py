import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# --- PROJECT ROOT ---
# This ensures paths work regardless of where you run the script from
BASE_DIR = Path(__file__).resolve().parent.parent

# --- API KEYS & LIMITS ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
DAILY_CHAPTER_LIMIT = int(os.getenv("DAILY_CHAPTER_LIMIT", 200))
TARGET_MODEL = os.getenv("TARGET_MODEL", "gemini-2.5-flash")

# --- DIRECTORY STRUCTURE ---
DATA_DIR = BASE_DIR / "data"
METADATA_BASE = DATA_DIR / "metadata"
ARTIFACT_BASE = DATA_DIR / "artifacts"
SUMMARY_BASE = DATA_DIR / "summaries"

# --- HELPER LOGIC (The "SSoT" for Slug Naming) ---
def get_safe_title(title: str) -> str:
    """The one and only place title slugging logic is defined."""
    return "".join([c for c in title if c.isalpha() or c.isspace()]).replace(" ", "_").lower()

def get_paths(title: str, chapter: str):
    """Returns a dictionary of all relevant paths for a specific chapter."""
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