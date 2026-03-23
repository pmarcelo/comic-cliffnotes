import os
import json
from datetime import datetime

LOG_FILE = "./data/usage_log.json"
# Set your "Safety Limit" (e.g., 100 chapters per day)
DAILY_LIMIT = 200 

def check_usage():
    """Returns True if it's safe to run, False if limit reached."""
    if not os.path.exists(LOG_FILE):
        return True
        
    today = datetime.now().strftime("%Y-%m-%d")
    with open(LOG_FILE, "r") as f:
        data = json.load(f)
        
    usage_today = data.get(today, 0)
    if usage_today >= DAILY_LIMIT:
        print(f"🛑 SAFETY LIMIT: You have processed {usage_today} chapters today.")
        print(f"To override, increase DAILY_LIMIT in core/usage_tracker.py")
        return False
    return True

def log_success():
    """Increments today's count in the log file."""
    today = datetime.now().strftime("%Y-%m-%d")
    data = {}
    
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, "r") as f:
            data = json.load(f)
            
    data[today] = data.get(today, 0) + 1
    
    with open(LOG_FILE, "w") as f:
        json.dump(data, f, indent=2)