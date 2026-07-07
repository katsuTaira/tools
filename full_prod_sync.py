import os
import requests
import time
import re
from datetime import datetime

# --- Settings ---
OPEN_WEBUI_BASE_URL = "https://open-webui2.kpssys.com/api/v1"
API_KEY = "sk-517492096074459c82eea231b6af3c5f"
TIMEOUT = 600

# KB IDs
KPS_NEWS_KB_ID = "63afb4f7-3e4e-46d6-8340-21cab281631b"
RULES_KB_ID = "a5191340-85ed-4ae1-a22d-83e7fcabbcd5"

# Local Directories
KPS_NEWS_DIR = "/mnt/c/Users/K00013/KPS新聞/"
RULES_DIR = "/mnt/c/Users/K00013/OneDrive/ドキュメント/qa_poc_light/output"

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Accept": "application/json"
}

def is_target_news_file(filename):
    """2022年4月以降のPDFファイルかどうかを判定"""
    if not filename.endswith('.pdf'):
        return False
    match = re.search(r'(\d{4})\.(\d{1,2})', filename)
    if match:
        year = int(match.group(1))
        month = int(match.group(2))
        if year > 2022: return True
        if year == 2022 and month >= 4: return True
    return False

def get_existing_kb_files(kb_id):
    """ナレッジベース内の既存ファイル名リストを取得"""
    url = f"{OPEN_WEBUI_BASE_URL}/knowledge/{kb_id}/files"
    try:
        response = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        if response.status_code != 200:
            print(f"  Error getting KB {kb_id} files: {response.text}")
            return []
        res_data = response.json()
        files = res_data.get('items', [])
        return [f.get('meta', {}).get('name', f.get('filename')) for f in files if isinstance(f, dict)]
    except Exception as e:
        print(f"  Error getting KB {kb_id} files: {e}")
        return []

def upload_and_process_file(file_path, kb_id):
    filename = os.path.basename(file_path)
    print(f" Processing: {filename}...")
    
    # 1. Upload
    url_upload = f"{OPEN_WEBUI_BASE_URL}/files/"
    try:
        with open(file_path, 'rb') as f:
            files = {'file': f}
            response = requests.post(url_upload, headers=HEADERS, files=files, timeout=TIMEOUT)
        
        if response.status_code != 200:
            print(f"  Error uploading: {response.text}")
            return False
        
        file_id = response.json().get('id')
        if not file_id:
            return False

        # 2. Polling
        for _ in range(30): # Max 5 mins
            status_res = requests.get(f"{OPEN_WEBUI_BASE_URL}/files/{file_id}", headers=HEADERS, timeout=TIMEOUT)
            if status_res.status_code == 200:
                data = status_res.json().get('data', {})
                if data.get('status') == 'completed':
                    break
                elif data.get('status') == 'failed':
                    print(f"  Processing failed: {data.get('error')}")
                    return False
            time.sleep(10)
        else:
            print(f"  Timeout waiting for processing.")
            return False

        # 3. Add to KB
        url_add = f"{OPEN_WEBUI_BASE_URL}/knowledge/{kb_id}/file/add"
        payload = {"file_id": file_id}
        add_res = requests.post(url_add, headers=HEADERS, json=payload, timeout=TIMEOUT)
        return add_res.status_code == 200

    except Exception as e:
        print(f"  Exception: {e}")
        return False

def sync_knowledge_base(directory, kb_id, filter_func=None):
    print(f"\n--- Syncing Directory: {directory} to KB: {kb_id} ---")
    existing_files = get_existing_kb_files(kb_id)
    print(f" Found {len(existing_files)} existing files in KB.")
    
    all_local_files = os.listdir(directory)
    files_to_upload = [f for f in all_local_files if (filter_func(f) if filter_func else True) and f not in existing_files]
    
    print(f" Found {len(files_to_upload)} new files to upload.")
    count = 0
    for filename in files_to_upload:
        if upload_and_process_file(os.path.join(directory, filename), kb_id):
            print(f"  Successfully registered: {filename}")
            count += 1
        else:
            print(f"  Failed to process: {filename}")
    
    print(f" Sync complete. {count} files processed.")

if __name__ == "__main__":
    print(f"--- Full Sync started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---")
    
    # 1. Sync KPS新聞
    sync_knowledge_base(KPS_NEWS_DIR, KPS_NEWS_KB_ID, is_target_news_file)
    
    # 2. Sync 就業規則 (All files in directory)
    sync_knowledge_base(RULES_DIR, RULES_KB_ID, None)
    
    print(f"\n--- All tasks completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---")
