import json
from pathlib import Path
from datetime import datetime

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
LOG_FILE = ROOT_DIR / "data" / "usage_log.json"

# --- TIER-SPECIFIC LIMITS ---
# Google AI Studio Free Tier limits vary drastically by model size.
LIMITS = {
    "flash": {
        "tokens": 1_000_000, 
        "chapters": 200
    },
    "pro": {
        "tokens": 100_000,  # Pro uses tokens much faster; limit acts as a cost/quota safeguard
        "chapters": 45      # Free tier limit is 50 requests/day
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

def check_usage(model_name: str) -> bool:
    """Returns True if safe to run based on the specific model's tier."""
    _ensure_log_exists()
    tier = _get_tier(model_name)
    limits = LIMITS[tier]
        
    today = datetime.now().strftime("%Y-%m-%d")
    with open(LOG_FILE, "r") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            data = {}
            
    # Look for today's stats under the specific tier
    today_stats = data.get(today, {}).get(tier, {"chapters": 0, "tokens": 0})
    
    if today_stats["chapters"] >= limits["chapters"]:
        print(f"🛑 {tier.upper()} LIMIT: Reached {today_stats['chapters']} chapters today.")
        return False
        
    if today_stats["tokens"] >= limits["tokens"]:
        print(f"🛑 {tier.upper()} QUOTA: Reached {today_stats['tokens']:,} tokens today.")
        return False
        
    return True

def log_success(tokens_used: int = 0, model_name: str = "default"):
    """Logs usage under the correct model tier."""
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

def get_today_tokens(model_name: str) -> dict:
    """Returns the tokens used and the max limit for the given model."""
    tier = _get_tier(model_name)
    max_limit = LIMITS[tier]["tokens"]
    
    if not LOG_FILE.exists():
        return {"used": 0, "limit": max_limit}
        
    today = datetime.now().strftime("%Y-%m-%d")
    try:
        with open(LOG_FILE, "r") as f:
            data = json.load(f)
            used = data.get(today, {}).get(tier, {}).get("tokens", 0)
            return {"used": used, "limit": max_limit}
    except Exception:
        return {"used": 0, "limit": max_limit}