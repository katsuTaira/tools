import os
import requests
import time
import sys

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

def upload_and_process_file(file_path, kb_id):
    filename = os.path.basename(file_path)
    print(f"--- Processing: {filename} ---")
    
    # 1. Upload
    print(f"  Uploading...")
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
            print("  Error: No file_id returned.")
            return False

        # 2. Wait for processing (Polling)
        print(f"  Waiting for backend processing...")
        for i in range(30): # Max 5 mins
            status_res = requests.get(f"{OPEN_WEBUI_BASE_URL}/files/{file_id}", headers=HEADERS, timeout=TIMEOUT)
            if status_res.status_code == 200:
                data = status_res.json().get('data', {})
                status = data.get('status')
                if status == 'completed':
                    print(f"  Processing completed.")
                    break
                elif status == 'failed':
                    print(f"  Processing failed: {data.get('error')}")
                    return False
            else:
                print(f"  Error checking status: {status_res.status_code}")
            time.sleep(10)
        else:
            print("  Timeout waiting for processing.")
            return False

        # 3. Add to Knowledge Base
        print(f"  Adding to Knowledge Base {kb_id}...")
        url_add = f"{OPEN_WEBUI_BASE_URL}/knowledge/{kb_id}/file/add"
        payload = {"file_id": file_id}
        add_res = requests.post(url_add, headers=HEADERS, json=payload, timeout=TIMEOUT)
        
        if add_res.status_code == 200:
            print(f"  Successfully registered: {filename}")
            return True
        else:
            print(f"  Failed to register: {add_res.text}")
            return False

    except Exception as e:
        print(f"  Exception occurred: {e}")
        return False

if __name__ == "__main__":
    print(f"Starting Production Test Upload...")
    
    # Test 1: KPS新聞
    news_file = os.path.join(KPS_NEWS_DIR, "ＫＰＳ新聞2026.5.pdf")
    if os.path.exists(news_file):
        upload_and_process_file(news_file, KPS_NEWS_KB_ID)
    else:
        print(f"KPS News file not found: {news_file}")

    # Test 2: 就業規則
    rules_file = os.path.join(RULES_DIR, "01従業員就業規定（2025.03更新）.md")
    if os.path.exists(rules_file):
        upload_and_process_file(rules_file, RULES_KB_ID)
    else:
        print(f"Rules file not found: {rules_file}")
    
    print("Test upload complete.")
