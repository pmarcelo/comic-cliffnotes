import json
from pathlib import Path
from datetime import datetime

# Path setup relative to this file
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
LOG_FILE = ROOT_DIR / "data" / "usage_log.json"

# --- TIER-SPECIFIC LIMITS ---
LIMITS = {
    "flash": {
        "tokens": 1_000_000, 
        "chapters": 2000 # Increased for lite-preview tiers
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
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not LOG_FILE.exists():
        with open(LOG_FILE, "w") as f:
            json.dump({}, f)

def get_today_stats(model_name: str) -> dict:
    """
    Dashboard Helper: Returns formatted stats from the JSON log.
    Maps 'chapters' to 'requests' for the UI.
    """
    _ensure_log_exists()
    tier = _get_tier(model_name)
    today = datetime.now().strftime("%Y-%m-%d")
    
    try:
        with open(LOG_FILE, "r") as f:
            data = json.load(f)
            # Drill down: Date -> Tier -> Stats
            stats = data.get(today, {}).get(tier, {"chapters": 0, "tokens": 0})
            
            return {
                "requests": stats["chapters"],  # Dashboard calls them 'requests'
                "tokens": stats["tokens"],
                "token_limit": LIMITS[tier]["tokens"]
            }
    except (json.JSONDecodeError, Exception):
        return {"requests": 0, "tokens": 0, "token_limit": LIMITS[tier]["tokens"]}

def check_usage(model_name: str) -> bool:
    """Logic gate for processor.py."""
    stats = get_today_stats(model_name)
    tier = _get_tier(model_name)
    limits = LIMITS[tier]
    
    if stats["requests"] >= limits["chapters"]:
        print(f"🛑 {tier.upper()} LIMIT: Reached {stats['requests']} requests today.")
        return False
        
    if stats["tokens"] >= limits["tokens"]:
        print(f"🛑 {tier.upper()} QUOTA: Reached {stats['tokens']:,} tokens today.")
        return False
        
    return True

def log_success(tokens_used: int = 0, model_name: str = "default"):
    """Increments the count in your JSON file."""
    _ensure_log_exists()
    tier = _get_tier(model_name)
    today = datetime.now().strftime("%Y-%m-%d")
    
    with open(LOG_FILE, "r") as f:
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
    
    with open(LOG_FILE, "w") as f:
        json.dump(data, f, indent=2)

# Keep this for backward compatibility if any old code uses it
def get_today_tokens(model_name: str) -> dict:
    stats = get_today_stats(model_name)
    return {"used": stats["tokens"], "limit": stats["token_limit"]}