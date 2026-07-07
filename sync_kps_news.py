#!/usr/bin/env python3
import os
import json
import subprocess
import requests
import re
import time
from datetime import datetime

# --- 設定 ---
# gog 設定
GOG_PATH = "/home/linuxbrew/.linuxbrew/bin/gog"
ACCOUNT = "katsusuke.taira@kpscorp.co.jp"

# Google Drive
DRIVE_PARENT_FOLDER_ID = "17od521b_rBrYI2F8ovNJDWyCTMS3Idk5"
LOCAL_DIR = "/mnt/c/Users/K00013/KPS新聞/"

# Open WebUI (Production)
OPEN_WEBUI_BASE_URL = "https://open-webui2.kpssys.com/api/v1"
API_KEY = "sk-517492096074459c82eea231b6af3c5f"
#KNOWLEDGE_ID = "932fab48-7b18-4749-afb6-700996b70cd9"
KNOWLEDGE_ID = "63afb4f7-3e4e-46d6-8340-21cab281631b"

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Accept": "application/json"
}

TIMEOUT = 600  # 10 minutes

def is_target_file(filename):
    """2022年4月以降のPDFファイルかどうかを判定"""
    if not filename.endswith('.pdf'):
        return False
    match = re.search(r'(\d{4})\.(\d{1,2})', filename)
    if match:
        year = int(match.group(1))
        month = int(match.group(2))
        if year > 2022:
            return True
        if year == 2022 and month >= 4:
            return True
    return False

def run_gog(args):
    """gogコマンドをアカウント指定と空パスワードで実行"""
    env = os.environ.copy()
    env["GOG_KEYRING_PASSWORD"] = ""
    cmd = [GOG_PATH, "-a", ACCOUNT] + args
    result = subprocess.run(cmd, capture_output=True, text=True, env=env)
    return result

# --- Google Drive 処理 ---

def get_drive_subfolders(parent_id):
    """サブフォルダの一覧を取得"""
    result = run_gog(["ls", "--parent", parent_id, "--json", "--results-only"])
    if result.returncode != 0:
        print(f"Error listing subfolders: {result.stderr}")
        return []
    return [f for f in json.loads(result.stdout) if f['mimeType'] == 'application/vnd.google-apps.folder']

def get_pdfs_in_folder(folder_id):
    """指定フォルダ内のPDF一覧を取得"""
    result = run_gog(["ls", "--parent", folder_id, "--json", "--results-only"])
    if result.returncode != 0:
        return []
    return [f for f in json.loads(result.stdout) if f['mimeType'] == 'application/pdf']

def download_missing_pdfs():
    """Drive上のPDFをチェックし、ローカルにないものをダウンロード"""
    print("Checking Google Drive for new PDF files...")
    subfolders = get_drive_subfolders(DRIVE_PARENT_FOLDER_ID)
    downloaded_count = 0

    for folder in subfolders:
        print(f" Scanning folder: {folder['name']}...")
        pdfs = get_pdfs_in_folder(folder['id'])
        for pdf in pdfs:
            if not is_target_file(pdf['name']):
                continue
            local_path = os.path.join(LOCAL_DIR, pdf['name'])
            if not os.path.exists(local_path):
                print(f"  Downloading new file: {pdf['name']}...")
                dl_res = run_gog(["download", pdf['id'], "--output", local_path])
                if dl_res.returncode == 0:
                    downloaded_count += 1
                else:
                    print(f"   Failed to download {pdf['name']}: {dl_res.stderr}")
    
    print(f"Google Drive sync complete. {downloaded_count} files downloaded.")

# --- Open WebUI 処理 ---

def get_existing_kb_files():
    """ナレッジベース内の既存ファイル名リストを取得"""
    # ページネーション対応: 全件取得する
    files = []
    page = 1
    per_page = 100
    try:
        while True:
            url = f"{OPEN_WEBUI_BASE_URL}/knowledge/{KNOWLEDGE_ID}/files?page={page}&per_page={per_page}"
            response = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
            if response.status_code != 200:
                print(f" Error getting KB files (page {page}): {response.text}")
                break

            res_data = response.json()
            items = res_data.get('items', [])
            if not items:
                break

            for f in items:
                if isinstance(f, dict):
                    files.append(f.get('meta', {}).get('name', f.get('filename')))

            # API が返す total フィールドがあればそれで完了判定
            total = res_data.get('total')
            if isinstance(total, int):
                if len(files) >= total:
                    break
                else:
                    page += 1
                    continue

            # total が無ければフォールバックで判定
            if len(items) < per_page:
                break
            page += 1

        return files
    except Exception as e:
        print(f" Error getting KB files: {e}")
        return []

def upload_file_to_ui(file_path):
    """ファイルをアップロードして処理完了まで待機し、file_id を取得"""
    url = f"{OPEN_WEBUI_BASE_URL}/files/"
    try:
        with open(file_path, 'rb') as f:
            files = {'file': f}
            response = requests.post(url, headers=HEADERS, files=files, timeout=TIMEOUT)
        
        if response.status_code != 200:
            print(f" Error uploading {os.path.basename(file_path)}: {response.text}")
            return None
        
        file_id = response.json().get('id')
        if not file_id:
            return None

        # 処理完了を待機 (ポーリング)
        print(f"  Waiting for processing: {os.path.basename(file_path)}...")
        for _ in range(30):  # 最大5分 (10秒 * 30)
            status_res = requests.get(f"{OPEN_WEBUI_BASE_URL}/files/{file_id}", headers=HEADERS, timeout=TIMEOUT)
            if status_res.status_code == 200:
                data = status_res.json().get('data', {})
                status = data.get('status')
                if status == 'completed':
                    print(f"  Processing completed: {os.path.basename(file_path)}")
                    return file_id
                elif status == 'failed':
                    print(f"  Processing failed: {os.path.basename(file_path)} - {data.get('error', 'Unknown error')}")
                    return None
            time.sleep(10)
        
        print(f"  Timeout waiting for processing: {os.path.basename(file_path)}")
        return None

    except Exception as e:
        print(f" Error uploading {os.path.basename(file_path)}: {e}")
        return None

def add_file_to_knowledge(file_id):
    """file_id をナレッジベースに追加"""
    url = f"{OPEN_WEBUI_BASE_URL}/knowledge/{KNOWLEDGE_ID}/file/add"
    payload = {"file_id": file_id}
    try:
        response = requests.post(url, headers=HEADERS, json=payload, timeout=TIMEOUT)
        return response.status_code == 200
    except Exception as e:
        print(f" Error adding to KB: {e}")
        return False

def sync_to_open_webui():
    """ローカルのPDFをOpen WebUIに同期"""
    print(f"Syncing local files to Open WebUI Production ({OPEN_WEBUI_BASE_URL})...")
    existing_filenames = get_existing_kb_files()
    
    local_files = [f for f in os.listdir(LOCAL_DIR) if is_target_file(f)]
    files_to_upload = [f for f in local_files if f not in existing_filenames]

    if not files_to_upload:
        print(" No new files to upload to Open WebUI.")
        return

    print(f" Found {len(files_to_upload)} new files to upload.")
    uploaded_count = 0

    for filename in files_to_upload:
        file_path = os.path.join(LOCAL_DIR, filename)
        print(f" Processing: {filename}...")
        
        file_id = upload_file_to_ui(file_path)
        if file_id:
            if add_file_to_knowledge(file_id):
                print(f"  Successfully registered: {filename}")
                uploaded_count += 1
            else:
                print(f"  Failed to register {filename} to knowledge base.")
        else:
            print(f"  Failed to upload or process {filename}.")
    
    print(f"Open WebUI sync complete. {uploaded_count} files processed.")

def main():
    print(f"--- Task started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---")
    if not os.path.exists(LOCAL_DIR):
        os.makedirs(LOCAL_DIR, exist_ok=True)

    # 1. Google Drive -> Local
    download_missing_pdfs()

    # 2. Local -> Open WebUI
    sync_to_open_webui()

if __name__ == "__main__":
    main()
