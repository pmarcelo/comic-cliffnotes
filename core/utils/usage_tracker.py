import os
import json
from pathlib import Path
from datetime import datetime

# --- DYNAMIC LOG PATHING ---
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
# Constructed based on the active project
PROJECT_NAME = os.getenv("GEMINI_PROJECT", "default")
LOG_FILE = ROOT_DIR / "data" / f"usage_log_{PROJECT_NAME}.json"

# --- TIER-SPECIFIC LIMITS ---
LIMITS = {
    "flash": {
        "tokens": 1_000_000, 
        "chapters": 2000 
    },
    "pro": {
        "tokens": 100_000,
        "chapters": 50
    }
}

def _get_tier(model_name: str) -> str:
    """Classifies the model into its quota bucket."""
    if not model_name: return "flash"
    return "pro" if "pro" in model_name.lower() else "flash"

def _ensure_log_exists():
    """Ensures the data directory and project-specific JSON exist."""
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not LOG_FILE.exists():
        with open(LOG_FILE, "w", encoding="utf-8") as f:
            json.dump({}, f)

def get_today_stats(model_name: str) -> dict:
    """
    Dashboard Helper: Returns formatted stats from the project-specific JSON log.
    """
    _ensure_log_exists()
    tier = _get_tier(model_name)
    today = datetime.now().strftime("%Y-%m-%d")
    
    try:
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            # Drill down: Date -> Tier -> Stats
            day_data = data.get(today, {})
            stats = day_data.get(tier, {"chapters": 0, "tokens": 0})
            
            return {
                "requests": stats["chapters"],  
                "tokens": stats["tokens"],
                "token_limit": LIMITS[tier]["tokens"],
                "project": PROJECT_NAME # Useful for dashboard display
            }
    except (json.JSONDecodeError, Exception):
        return {
            "requests": 0, 
            "tokens": 0, 
            "token_limit": LIMITS[tier]["tokens"],
            "project": PROJECT_NAME
        }

def check_usage(model_name: str) -> bool:
    """Logic gate for processor.py."""
    stats = get_today_stats(model_name)
    tier = _get_tier(model_name)
    limits = LIMITS[tier]
    
    if stats["requests"] >= limits["chapters"]:
        print(f"[{PROJECT_NAME.upper()}] {tier.upper()} LIMIT: Reached {stats['requests']} requests.")
        return False
        
    if stats["tokens"] >= limits["tokens"]:
        print(f"[{PROJECT_NAME.upper()}] {tier.upper()} QUOTA: Reached {stats['tokens']:,} tokens.")
        return False
        
    return True

def log_success(tokens_used: int = 0, model_name: str = "default"):
    """Increments the count in the project-specific JSON file."""
    _ensure_log_exists()
    tier = _get_tier(model_name)
    today = datetime.now().strftime("%Y-%m-%d")
    
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            data = {}
            
    if today not in data:
        data[today] = {}
    if tier not in data[today]:
        data[today][tier] = {"chapters": 0, "tokens": 0}
        
    data[today][tier]["chapters"] += 1
    data[today][tier]["tokens"] += tokens_used
    
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def get_today_tokens(model_name: str) -> dict:
    """Backward compatibility helper."""
    stats = get_today_stats(model_name)
    return {"used": stats["tokens"], "limit": stats["token_limit"]}