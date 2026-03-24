import os
import json
import shutil
import subprocess
import logging
import zipfile
from pathlib import Path
from core import config

logger = logging.getLogger(__name__)

def get_safe_title(title: str) -> str:
    return "".join([c for c in title if c.isalpha() or c.isspace()]).replace(" ", "_").lower()

def get_paths(title: str, chapter: str):
    slug = get_safe_title(title)
    paths = {
        "metadata": config.METADATA_BASE / slug / f"ch{chapter}_metadata.json",
        "artifact": config.ARTIFACT_BASE / slug / f"ch{chapter}_artifact.json",
        "summary": config.SUMMARY_BASE / slug / f"ch{chapter}_summary.json",
        "manifest": config.SUMMARY_BASE / slug / "manifest.json",
        "title_dir": config.SUMMARY_BASE / slug
    }
    paths["metadata"].parent.mkdir(parents=True, exist_ok=True)
    paths["artifact"].parent.mkdir(parents=True, exist_ok=True)
    paths["summary"].parent.mkdir(parents=True, exist_ok=True)
    return paths

def ensure_directory(path: str | Path):
    Path(path).mkdir(parents=True, exist_ok=True)

def cleanup_directory(path: str | Path):
    if os.path.exists(path):
        shutil.rmtree(path)

def load_json(path: str | Path):
    if not os.path.exists(path):
        return None
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_json(data: dict, path: str | Path):
    ensure_directory(os.path.dirname(path))
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def run_command(command: list) -> bool:
    logger.info(f"🛠️ Executing: {' '.join(command)}")
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    for line in process.stdout:
        print(line, end="")
    process.wait()
    return process.returncode == 0

def extract_archive(archive_path: str, extract_dir: str):
    ensure_directory(extract_dir)
    try:
        with zipfile.ZipFile(archive_path, 'r') as zip_ref:
            zip_ref.extractall(extract_dir)
        return True
    except Exception as e:
        logger.error(f"Failed to extract archive: {e}")
        return False