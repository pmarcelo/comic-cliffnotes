import time
import subprocess
import sys
import os
from pathlib import Path
from datetime import datetime, timezone
from sqlalchemy import select

# 🎯 FIX: Add the project root to sys.path so 'database' and 'core' can be found
root_path = Path(__file__).resolve().parent.parent.parent
if str(root_path) not in sys.path:
    sys.path.insert(0, str(root_path))

from database.session import SessionLocal
from database.models import ProcessingQueue, QueueStatus, Series

# --- Rest of the worker logic ---

POLL_INTERVAL = 10 

def log(message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}")

def run_worker(lane=None):
    log(f"Worker started. Lane: {lane if lane else 'ALL'}")
    
    while True:
        db = SessionLocal()
        try:
            # We look for PENDING tasks (using the Enum which SQLAlchemy handles)
            query = select(ProcessingQueue).where(ProcessingQueue.status == QueueStatus.PENDING)
            
            if lane:
                query = query.where(ProcessingQueue.action == lane)
            
            query = query.order_by(ProcessingQueue.priority, ProcessingQueue.created_at)
            task = db.execute(query).scalars().first()

            if not task:
                db.close()
                time.sleep(POLL_INTERVAL)
                continue

            # Claim the task
            series_title = task.series.title
            task.status = QueueStatus.RUNNING
            task.updated_at = datetime.now(timezone.utc)
            db.commit()
            
            log(f"Picking up: {task.action.upper()} for '{series_title}'")

            # Build Command
            cmd = [sys.executable, "processor.py", "-t", series_title]
            
            if task.action == "ocr":
                cmd.append("--ocr")
            elif task.action == "summary":
                cmd.append("--summarize")
            elif task.action == "extract":
                cmd.append("--extract")
            
            if task.context and "model" in task.context:
                cmd.extend(["--model", task.context["model"]])

            # Execute Subprocess
            try:
                # Ensure the subprocess also has the correct PYTHONPATH
                env = {**os.environ, "PYTHONPATH": str(root_path)}
                result = subprocess.run(cmd, env=env, capture_output=True, text=True)

                if result.returncode == 0:
                    task.status = QueueStatus.COMPLETED
                    task.error_log = None
                    log(f"COMPLETED: {task.action} for '{series_title}'")
                else:
                    task.status = QueueStatus.FAILED
                    task.error_log = result.stderr or result.stdout
                    log(f"FAILED: {task.action} for '{series_title}'")
            except Exception as e:
                task.status = QueueStatus.FAILED
                task.error_log = str(e)
                log(f"SYSTEM ERROR: {e}")

            task.updated_at = datetime.now(timezone.utc)
            db.commit()

        except Exception as e:
            log(f"CRITICAL DB ERROR: {e}")
            db.rollback()
        finally:
            db.close()
            
        time.sleep(2)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--lane", help="Specific action lane to watch (ocr, summary, extract)")
    args = parser.parse_args()
    
    run_worker(lane=args.lane)