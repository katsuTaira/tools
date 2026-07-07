#!/usr/bin/env python3
import os
import json
import subprocess
import requests
import re
from datetime import datetime

# --- 設定 (テスト環境用) ---
GOG_PATH = "/home/linuxbrew/.linuxbrew/bin/gog"
ACCOUNT = "katsusuke.taira@kpscorp.co.jp"

# Google Drive (そのまま)
DRIVE_PARENT_FOLDER_ID = "17od521b_rBrYI2F8ovNJDWyCTMS3Idk5"
LOCAL_DIR = "/mnt/c/Users/K00013/KPS新聞/"

# Open WebUI (テスト環境の設定)
OPEN_WEBUI_BASE_URL = "https://open-webuit.kpssys.com/api/v1"
API_KEY = "sk-517492096074459c82eea231b6af3c5f"
KNOWLEDGE_ID = "932fab48-7b18-4749-afb6-700996b70cd9"

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Accept": "application/json"
}

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

# --- Open WebUI 処理 ---

TIMEOUT = 600  # 10 minutes

def get_knowledge_base_data():
    """ナレッジ一覧から対象のデータを取得"""
    url = f"{OPEN_WEBUI_BASE_URL}/knowledge/"
    try:
        response = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        if response.status_code != 200:
            return None
        
        # 構造が変わっている可能性に対応
        res_data = response.json()
        kb_list = res_data.get('items', res_data) if isinstance(res_data, dict) else res_data
        return next((kb for kb in kb_list if kb['id'] == KNOWLEDGE_ID), None)
    except Exception as e:
        print(f" Error getting knowledge base data: {e}")
        return None

def get_existing_kb_files():
    """ナレッジベース内の既存ファイル名リストを取得"""
    url = f"{OPEN_WEBUI_BASE_URL}/knowledge/{KNOWLEDGE_ID}/files"
    try:
        response = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        if response.status_code != 200:
            print(f" Error getting KB files: {response.text}")
            return []
        
        res_data = response.json()
        files = res_data.get('items', [])
        return [f.get('meta', {}).get('name', f.get('filename')) for f in files if isinstance(f, dict)]
    except Exception as e:
        print(f" Error getting KB files: {e}")
        return []

import time

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
                    print(f"  Processing failed: {os.path.basename(file_path)} - {data.get('error')}")
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
        if response.status_code == 200:
            return True
        print(f" Error adding to KB: {response.text}")
        return False
    except Exception as e:
        print(f" Error adding to KB: {e}")
        return False

def reindex_all_knowledge():
    """すべてのナレッジベースの再インデックスをトリガーする"""
    print("Triggering all Knowledge Bases reindex...")
    url = f"{OPEN_WEBUI_BASE_URL}/knowledge/reindex"
    try:
        # reindex はレスポンスが返ってこない場合があるため、タイムアウトを短めにして例外を許容する
        requests.post(url, headers=HEADERS, timeout=5)
        print(" Reindex request sent.")
    except requests.exceptions.ReadTimeout:
        print(" Reindex request sent (ReadTimeout as expected).")
    except Exception as e:
        print(f" Reindex request status: {e}")

def sync_to_open_webui():
    """ローカルのPDFをOpen WebUIに同期"""
    print(f"Syncing local files to Open WebUI Test Env ({OPEN_WEBUI_BASE_URL})...")
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
    if uploaded_count > 0:
        reindex_all_knowledge()

def main():
    print(f"--- Sync (Test Env) started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---")
    if not os.path.exists(LOCAL_DIR):
        print(f"Error: LOCAL_DIR {LOCAL_DIR} not found.")
        return
    sync_to_open_webui()

if __name__ == "__main__":
    main()
