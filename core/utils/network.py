import os
import re
import shutil
import time
import logging
import requests
import concurrent.futures

logger = logging.getLogger(__name__)

def download_image(session: requests.Session, url: str, path: str, retries: int = 3) -> bool:
    for i in range(retries):
        try:
            res = session.get(url, timeout=15)
            if res.status_code == 200:
                with open(path, 'wb') as f: 
                    f.write(res.content)
                return True
        except Exception:
            if i == retries - 1: return False
    return False

def download_gdrive(url: str, output_path: str, num_threads: int = 4) -> bool:
    """
    Optimized multi-threaded Google Drive downloader. 
    Uses 4 concurrent connections to maximize bandwidth without triggering rate limits.
    """
    print(f"☁️ Connecting to Google Drive...")
    try:
        # 1. Extract the unique file ID from the Google Drive URL
        file_id_match = re.search(r'/d/([a-zA-Z0-9_-]+)', url)
        file_id = file_id_match.group(1) if file_id_match else url.split('id=')[-1]
        
        session = requests.Session()
        base_url = "https://docs.google.com/uc?export=download"
        
        response = session.get(base_url, params={'id': file_id}, stream=True)
        
        # 2. Handle Google's "Large File" Virus Scan Warning
        token = None
        for key, value in response.cookies.items():
            if key.startswith('download_warning'):
                token = value
                break
                
        if token:
            # Re-request with the confirmation token
            response = session.get(base_url, params={'id': file_id, 'confirm': token}, stream=True)
            
        total_size = int(response.headers.get('Content-Length', 0))
        
        # Fallback: Sometimes Google hides the Content-Length. If they do, we can't chunk it.
        if total_size == 0:
            print("⚠️ Unknown file size. Falling back to safe single-threaded download...")
            with open(output_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            return True

        print(f"🚀 File size: {total_size / (1024*1024):.2f} MB. Engaging {num_threads}-thread accelerated download...")
        
        # 3. Mathematical Chunking Setup
        chunk_size = total_size // num_threads
        part_files = []
        
        def download_chunk(part_num, start, end):
            """Worker thread logic: Requests a specific byte range from Google."""
            headers = {"Range": f"bytes={start}-{end}"}
            part_path = f"{output_path}.part{part_num}"
            
            params = {'id': file_id}
            if token: 
                params['confirm'] = token
            
            res = session.get(base_url, params=params, headers=headers, stream=True)
            
            with open(part_path, "wb") as f:
                for chunk in res.iter_content(chunk_size=1024*1024): # 1MB memory chunks
                    if chunk: 
                        f.write(chunk)
            return part_path

        # 4. Fire up the Thread Pool
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = []
            for i in range(num_threads):
                start = i * chunk_size
                # Ensure the very last thread grabs everything up to the final byte
                end = start + chunk_size - 1 if i < num_threads - 1 else total_size - 1
                
                # Add a tiny 200ms stagger between thread launches to prevent connection spikes
                time.sleep(0.2) 
                futures.append(executor.submit(download_chunk, i, start, end))
            
            # Wait for all pipes to finish downloading their pieces
            for future in concurrent.futures.as_completed(futures):
                part_files.append(future.result())

        # 5. Stitch them back together
        print("🧵 Stitching chunks together...")
        # Ensure we stitch them in order: part0, part1, part2...
        part_files.sort(key=lambda x: int(x.split('.part')[-1])) 
        
        with open(output_path, "wb") as outfile:
            for part in part_files:
                with open(part, "rb") as infile:
                    shutil.copyfileobj(infile, outfile)
                os.remove(part) # Clean up the temporary part file
                
        return os.path.exists(output_path)

    except Exception as e:
        logger.error(f"Google Drive download failed: {e}")
        return False

def download_direct_file(url: str, output_path: str) -> bool:
    print(f"☁️ Downloading direct file...")
    try:
        if "dropbox.com" in url and "dl=0" in url:
            url = url.replace("dl=0", "dl=1")
            
        res = requests.get(url, stream=True)
        res.raise_for_status()
        with open(output_path, 'wb') as f:
            for chunk in res.iter_content(chunk_size=8192):
                f.write(chunk)
        return True
    except Exception as e:
        logger.error(f"Direct download failed: {e}")
        return False