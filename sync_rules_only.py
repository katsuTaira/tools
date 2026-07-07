import os
import requests
import time
from datetime import datetime

# --- Settings ---
OPEN_WEBUI_BASE_URL = "https://open-webui2.kpssys.com/api/v1"
API_KEY = "sk-517492096074459c82eea231b6af3c5f"
TIMEOUT = 600

# KB ID for 就業規則
RULES_KB_ID = "a5191340-85ed-4ae1-a22d-83e7fcabbcd5"

# Local Directory
RULES_DIR = "/mnt/c/Users/K00013/OneDrive/ドキュメント/qa_poc_light/output"

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Accept": "application/json"
}

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
            # Handle potential duplicate content error gracefully
            if "Duplicate content" in response.text:
                print(f"  Skip (Duplicate content): {filename}")
                return True
            print(f"  Error uploading: {response.text}")
            return False
        
        file_id = response.json().get('id')
        if not file_id:
            return False

        # 2. Polling
        print(f"  Waiting for processing...")
        for _ in range(30):
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
        if add_res.status_code == 200:
            print(f"  Successfully registered: {filename}")
            return True
        else:
            if "Duplicate content" in add_res.text:
                print(f"  Skip (Duplicate in KB): {filename}")
                return True
            print(f"  Failed to register: {add_res.text}")
            return False

    except Exception as e:
        print(f"  Exception: {e}")
        return False

def sync_rules():
    print(f"\n--- Syncing Directory: {RULES_DIR} ---")
    existing_files = get_existing_kb_files(RULES_KB_ID)
    print(f" Found {len(existing_files)} existing files in '就業規則' KB.")
    
    all_local_files = [f for f in os.listdir(RULES_DIR) if os.path.isfile(os.path.join(RULES_DIR, f))]
    files_to_upload = [f for f in all_local_files if f not in existing_files]
    
    print(f" Found {len(files_to_upload)} new files to upload.")
    count = 0
    for filename in files_to_upload:
        if upload_and_process_file(os.path.join(RULES_DIR, filename), RULES_KB_ID):
            count += 1
        time.sleep(2) # Small delay to be kind to the server
    
    print(f" Sync complete. {count} files processed successfully.")

if __name__ == "__main__":
    print(f"--- Rules Sync started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---")
    sync_rules()
    print(f"--- Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---")
