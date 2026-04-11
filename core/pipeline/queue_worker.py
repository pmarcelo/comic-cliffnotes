import time
import subprocess
import sys
import os
from pathlib import Path
from datetime import datetime, timezone
from sqlalchemy import select

# Add the project root to sys.path
root_path = Path(__file__).resolve().parent.parent.parent
if str(root_path) not in sys.path:
    sys.path.insert(0, str(root_path))

from database.session import SessionLocal
from database.models import ProcessingQueue, QueueStatus

# Configuration
POLL_INTERVAL = 10 

def log(message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # flush=True ensures logs print instantly to the console
    print(f"[{timestamp}] {message}", flush=True)

def run_worker(lane=None):
    """
    Worker loop with UTF-8 safe log streaming.
    """
    log(f"STARTUP: Worker started. Lane: {lane if lane else 'ALL'}")
    
    while True:
        db = SessionLocal()
        task = None
        try:
            # 1. Fetch Task
            # Strictly looks for PENDING to ignore UI's RUNNING "Ghost Tasks"
            query = select(ProcessingQueue).where(ProcessingQueue.status == QueueStatus.PENDING)
            if lane:
                query = query.where(ProcessingQueue.action == lane)
            
            query = query.order_by(ProcessingQueue.priority, ProcessingQueue.created_at)
            task = db.execute(query).scalars().first()

            if not task:
                db.close()
                time.sleep(POLL_INTERVAL)
                continue

            # 2. Claim the Task Safely
            # Double check status inside the transaction to prevent race conditions with the UI
            if task.status != QueueStatus.PENDING:
                db.close()
                continue
                
            series_title = task.series.title
            task_action = task.action.upper()
            task.status = QueueStatus.RUNNING
            task.updated_at = datetime.now(timezone.utc)
            db.commit()
            
            log(f"JOB START: {task_action} for '{series_title}'")

            # 3. Build Command
            cmd = [sys.executable, "processor.py", "-t", series_title]
            if task.action == "ocr":
                cmd.append("--ocr")
            elif task.action == "summary":
                cmd.append("--summarize")
            elif task.action == "extract":
                cmd.append("--extract")
            elif task.action == "full":
                cmd.extend(["--extract", "--ocr", "--summarize"])
            
            if task.context and "model" in task.context:
                cmd.extend(["--model", task.context["model"]])

            log(f"EXECUTING: {' '.join(cmd)}")

            # 4. Stream Logs Safely
            env = {**os.environ, "PYTHONPATH": str(root_path), "PYTHONUTF8": "1"}
            
            # Explicitly set encoding and error handling for the pipe
            process = subprocess.Popen(
                cmd, 
                env=env, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.STDOUT, 
                text=True,
                encoding='utf-8',
                errors='replace',
                bufsize=1,
                universal_newlines=True
            )

            full_output = []
            if process.stdout:
                for line in process.stdout:
                    clean_line = line.strip()
                    if clean_line:
                        print(f"  > {clean_line}", flush=True)
                        full_output.append(clean_line)
            
            process.wait()

            # 5. Finalize Task Status
            db.refresh(task)
            if process.returncode == 0:
                task.status = QueueStatus.COMPLETED
                task.error_log = None
                log(f"SUCCESS: {task_action} finished for '{series_title}'")
            else:
                task.status = QueueStatus.FAILED
                # Store the failure reason
                task.error_log = "\n".join(full_output[-20:]) if full_output else "Process exited with non-zero code."
                log(f"FAILURE: {task_action} failed for '{series_title}'")
            
            task.updated_at = datetime.now(timezone.utc)
            db.commit()

        except Exception as e:
            log(f"CRITICAL ERROR: {str(e)}")
            if db:
                db.rollback()
        finally:
            db.close()
            
        time.sleep(2)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--lane", help="Specific action lane to watch (ocr, summary, extract)")
    args = parser.parse_args()
    
    try:
        run_worker(lane=args.lane)
    except KeyboardInterrupt:
        log("SHUTDOWN: Worker stopped by user.")
        sys.exit(0)