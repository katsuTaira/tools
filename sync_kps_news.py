#!/usr/bin/env python3
import os
import json
import subprocess
import requests
import re
from datetime import datetime

# --- 設定 ---
# ... (rest of settings remains same)
# gog 設定
GOG_PATH = "/home/linuxbrew/.linuxbrew/bin/gog"
ACCOUNT = "katsusuke.taira@kpscorp.co.jp"

# Google Drive
DRIVE_PARENT_FOLDER_ID = "17od521b_rBrYI2F8ovNJDWyCTMS3Idk5"
LOCAL_DIR = "/mnt/c/Users/K00013/KPS新聞/"

# Open WebUI
OPEN_WEBUI_BASE_URL = "https://open-webui2.kpssys.com/api/v1"
API_KEY = "sk-bde765af6155408aa242542155945065"
KNOWLEDGE_ID = "932fab48-7b18-4749-afb6-700996b70cd9"

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Accept": "application/json"
}

def is_target_file(filename):
    """2022年4月以降のPDFファイルかどうかを判定"""
    if not filename.endswith('.pdf'):
        return False
    # ファイル名から 'YYYY.M' または 'YYYY.MM' を探す
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

TIMEOUT = 600  # 10 minutes

def get_knowledge_base_data():
    """ナレッジ一覧から対象のデータを取得"""
    url = f"{OPEN_WEBUI_BASE_URL}/knowledge/"
    try:
        response = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        if response.status_code != 200:
            return None
        
        kb_list = response.json()
        return next((kb for kb in kb_list if kb['id'] == KNOWLEDGE_ID), None)
    except requests.exceptions.Timeout:
        print(" Error: Timeout getting knowledge base data.")
        return None

def get_existing_kb_files():
    """ナレッジベース内の既存ファイル名リストを取得"""
    kb_data = get_knowledge_base_data()
    if not kb_data:
        return []
    return [f['meta']['name'] for f in kb_data.get('files', []) if 'meta' in f and 'name' in f['meta']]

def upload_file_to_ui(file_path):
    """ファイルをアップロードして file_id を取得"""
    url = f"{OPEN_WEBUI_BASE_URL}/files/"
    try:
        with open(file_path, 'rb') as f:
            files = {'file': f}
            response = requests.post(url, headers=HEADERS, files=files, timeout=TIMEOUT)
        
        if response.status_code != 200:
            print(f" Error uploading {os.path.basename(file_path)}: {response.text}")
            return None
        return response.json().get('id')
    except requests.exceptions.Timeout:
        print(f" Error: Timeout uploading {os.path.basename(file_path)}.")
        return None

def add_file_to_knowledge(file_id):
    """file_id をナレッジベースに追加"""
    # 基本の add エンドポイントを試す
    url = f"{OPEN_WEBUI_BASE_URL}/knowledge/{KNOWLEDGE_ID}/file/add"
    payload = {"file_id": file_id}
    try:
        response = requests.post(url, headers=HEADERS, json=payload, timeout=TIMEOUT)
        
        if response.status_code == 200:
            return True
    except requests.exceptions.Timeout:
        print(f" Error: Timeout adding file {file_id} to knowledge base.")
        return False
    
    # 失敗した場合は全体更新 (update) を試みるフォールバック
    kb_data = get_knowledge_base_data()
    if kb_data:
        file_ids = [f['id'] for f in kb_data.get('files', [])]
        if file_id not in file_ids:
            file_ids.append(file_id)
        
        url_update = f"{OPEN_WEBUI_BASE_URL}/knowledge/{KNOWLEDGE_ID}/update"
        update_payload = {
            "name": kb_data.get('name'),
            "description": kb_data.get('description'),
            "data": {"file_ids": file_ids}
        }
        try:
            res_update = requests.post(url_update, headers=HEADERS, json=update_payload, timeout=TIMEOUT)
            return res_update.status_code == 200
        except requests.exceptions.Timeout:
            print(f" Error: Timeout updating knowledge base with file {file_id}.")
            return False

    return False

def reindex_all_knowledge():
    """すべてのナレッジベースの再インデックスをトリガーする"""
    print("Triggering all Knowledge Bases reindex...")
    url = f"{OPEN_WEBUI_BASE_URL}/knowledge/reindex"
    try:
        response = requests.post(url, headers=HEADERS, timeout=TIMEOUT)
        if response.status_code == 200:
            print(" Successfully triggered reindex.")
            return True
        else:
            print(f" Failed to trigger reindex: {response.text}")
            return False
    except requests.exceptions.Timeout:
        print(" Error: Timeout triggering reindex.")
        return False

def sync_to_open_webui():
    """ローカルのPDFをOpen WebUIに同期"""
    print("Syncing local files to Open WebUI Knowledge Base...")
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
            print(f"  Failed to upload {filename}.")
    
    print(f"Open WebUI upload complete. {uploaded_count} files processed.")
    
    # 新たに追加したファイルがある場合のみ再インデックスを実行
    if uploaded_count > 0:
        reindex_all_knowledge()
    else:
        print(" No new files were successfully uploaded. Skipping reindex.")

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
