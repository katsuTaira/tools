#!/usr/bin/env python3
import os
import json
import subprocess
import requests
from datetime import datetime

# --- 設定 ---
# Google Drive
DRIVE_PARENT_FOLDER_ID = "17od521b_rBrYI2F8ovNJDWyCTMS3Idk5"
LOCAL_DIR = "/mnt/c/Users/K00013/KPS新聞/"

# Open WebUI
OPEN_WEBUI_BASE_URL = "https://open-webui2.kpssys.com/api/v1"
API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZCI6IjJjNmFkMjI0LTcwNTQtNDE1Zi1iNTJhLWUzZmYzODU2MjI4ZSIsImV4cCI6MTc3OTI2Mjk3OCwianRpIjoiZWE4YTQwMjQtNzdjNC00MWY0LWI5YWMtYjllNmE4MDg5ZWExIn0.aCcdnEywRxleYbvN3fXj8imuhj2aQnth9h-ykQ2vAY0"
KNOWLEDGE_ID = "61f39728-f32e-41f9-aed4-d543bac732d7"

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Accept": "application/json"
}

# --- Google Drive 処理 ---

def get_drive_subfolders(parent_id):
    """サブフォルダの一覧を取得"""
    cmd = ["gog", "ls", "--parent", parent_id, "--json", "--results-only"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error listing subfolders: {result.stderr}")
        return []
    return [f for f in json.loads(result.stdout) if f['mimeType'] == 'application/vnd.google-apps.folder']

def get_pdfs_in_folder(folder_id):
    """指定フォルダ内のPDF一覧を取得"""
    cmd = ["gog", "ls", "--parent", folder_id, "--json", "--results-only"]
    result = subprocess.run(cmd, capture_output=True, text=True)
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
            local_path = os.path.join(LOCAL_DIR, pdf['name'])
            if not os.path.exists(local_path):
                print(f"  Downloading new file: {pdf['name']}...")
                dl_cmd = ["gog", "download", pdf['id'], "--output", local_path]
                dl_res = subprocess.run(dl_cmd, capture_output=True, text=True)
                if dl_res.returncode == 0:
                    downloaded_count += 1
                else:
                    print(f"   Failed to download {pdf['name']}: {dl_res.stderr}")
    
    print(f"Google Drive sync complete. {downloaded_count} files downloaded.")

# --- Open WebUI 処理 ---

def get_knowledge_base_data():
    """ナレッジ一覧から対象のデータを取得"""
    url = f"{OPEN_WEBUI_BASE_URL}/knowledge/"
    response = requests.get(url, headers=HEADERS)
    if response.status_code != 200:
        return None
    
    kb_list = response.json()
    return next((kb for kb in kb_list if kb['id'] == KNOWLEDGE_ID), None)

def get_existing_kb_files():
    """ナレッジベース内の既存ファイル名リストを取得"""
    kb_data = get_knowledge_base_data()
    if not kb_data:
        return []
    return [f['meta']['name'] for f in kb_data.get('files', []) if 'meta' in f and 'name' in f['meta']]

def upload_file_to_ui(file_path):
    """ファイルをアップロードして file_id を取得"""
    url = f"{OPEN_WEBUI_BASE_URL}/files/"
    with open(file_path, 'rb') as f:
        files = {'file': f}
        response = requests.post(url, headers=HEADERS, files=files)
    
    if response.status_code != 200:
        print(f" Error uploading {os.path.basename(file_path)}: {response.text}")
        return None
    return response.json().get('id')

def add_file_to_knowledge(file_id):
    """file_id をナレッジベースに追加"""
    # 基本の add エンドポイントを試す
    url = f"{OPEN_WEBUI_BASE_URL}/knowledge/{KNOWLEDGE_ID}/file/add"
    payload = {"file_id": file_id}
    response = requests.post(url, headers=HEADERS, json=payload)
    
    if response.status_code == 200:
        return True
    
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
        res_update = requests.post(url_update, headers=HEADERS, json=update_payload)
        return res_update.status_code == 200

    return False

def sync_to_open_webui():
    """ローカルのPDFをOpen WebUIに同期"""
    print("Syncing local files to Open WebUI Knowledge Base...")
    existing_filenames = get_existing_kb_files()
    
    local_files = [f for f in os.listdir(LOCAL_DIR) if f.endswith('.pdf')]
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
    
    print(f"Open WebUI sync complete. {uploaded_count} files processed.")

def main():
    if not os.path.exists(LOCAL_DIR):
        os.makedirs(LOCAL_DIR, exist_ok=True)

    # 1. Google Drive -> Local
    download_missing_pdfs()

    # 2. Local -> Open WebUI
    sync_to_open_webui()

if __name__ == "__main__":
    main()
