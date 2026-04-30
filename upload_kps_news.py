import os
import requests
import json

# --- 設定 ---
BASE_URL = "https://open-webui2.kpssys.com/api/v1"
API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZCI6IjJjNmFkMjI0LTcwNTQtNDE1Zi1iNTJhLWUzZmYzODU2MjI4ZSIsImV4cCI6MTc3OTI2Mjk3OCwianRpIjoiZWE4YTQwMjQtNzdjNC00MWY0LWI5YWMtYjllNmE4MDg5ZWExIn0.aCcdnEywRxleYbvN3fXj8imuhj2aQnth9h-ykQ2vAY0"
KNOWLEDGE_ID = "61f39728-f32e-41f9-aed4-d543bac732d7"
LOCAL_DIR = "/mnt/c/Users/K00013/KPS新聞/"

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Accept": "application/json"
}

def get_existing_files():
    """ナレッジベース内の既存ファイル名リストを取得"""
    # curl で成功した末尾スラッシュありのURLを使用
    url = f"{BASE_URL}/knowledge/"
    response = requests.get(url, headers=HEADERS)
    if response.status_code != 200:
        print(f"Error getting knowledge list: {response.status_code}")
        return []
    
    try:
        kb_list = response.json()
        # 指定された KNOWLEDGE_ID のデータを探す
        kb_data = next((kb for kb in kb_list if kb['id'] == KNOWLEDGE_ID), None)
        if not kb_data:
            print(f"Knowledge ID {KNOWLEDGE_ID} not found in list.")
            return []
        
        return [f['meta']['name'] for f in kb_data.get('files', []) if 'meta' in f and 'name' in f['meta']]
    except Exception as e:
        print(f"Failed to parse JSON: {e}")
        print(f"Response snippet: {response.text[:200]}")
        return []

def upload_file(file_path):
    """ファイルをアップロードして file_id を取得"""
    url = f"{BASE_URL}/files/"
    with open(file_path, 'rb') as f:
        files = {'file': f}
        response = requests.post(url, headers=HEADERS, files=files)
    
    if response.status_code != 200:
        print(f"Error uploading file {os.path.basename(file_path)}: {response.text}")
        return None
    
    return response.json().get('id')

def add_file_to_knowledge(file_id):
    """file_id をナレッジベースに追加"""
    # 試行1: file_id を直接送る (以前失敗した形式だが再確認)
    # 試行2: file_ids (複数形) をリストで送る
    url = f"{BASE_URL}/knowledge/{KNOWLEDGE_ID}/file/add"
    payload = {"file_id": file_id}
    
    response = requests.post(url, headers=HEADERS, json=payload)
    
    if response.status_code == 200:
        return True
    
    # 試行3: ナレッジベースの更新 API を使用してみる
    # 既存のファイルリストを取得して、新しい ID を追加して更新する
    print(f"Retrying with knowledge update for {file_id}...")
    url_get = f"{BASE_URL}/knowledge/{KNOWLEDGE_ID}/"
    res_get = requests.get(url_get, headers=HEADERS)
    if res_get.status_code == 200:
        kb_data = res_get.json()
        # 既存のファイルIDリストを取得
        file_ids = [f['id'] for f in kb_data.get('files', [])]
        if file_id not in file_ids:
            file_ids.append(file_id)
        
        # update エンドポイント (POST /knowledge/{id}/update)
        url_update = f"{BASE_URL}/knowledge/{KNOWLEDGE_ID}/update"
        # 必須フィールド: name, description, data (file_ids を含む)
        update_payload = {
            "name": kb_data.get('name'),
            "description": kb_data.get('description'),
            "data": {"file_ids": file_ids}
        }
        res_update = requests.post(url_update, headers=HEADERS, json=update_payload)
        if res_update.status_code == 200:
            return True
        else:
            print(f"Update error: {res_update.text}")

    print(f"Add error: {response.text}")
    return False

def main():
    if not os.path.exists(LOCAL_DIR):
        print(f"Local directory not found: {LOCAL_DIR}")
        return

    print("Checking existing files in KPS新聞...")
    existing_filenames = get_existing_files()
    print(f"Found {len(existing_filenames)} files already in knowledge base.")

    # ローカルファイルを走査
    files_to_upload = [f for f in os.listdir(LOCAL_DIR) if f.endswith('.pdf') and f not in existing_filenames]

    if not files_to_upload:
        print("No new files to upload.")
        return

    print(f"Found {len(files_to_upload)} new files to upload.")

    for filename in files_to_upload:
        file_path = os.path.join(LOCAL_DIR, filename)
        print(f"Uploading: {filename}...")
        
        file_id = upload_file(file_path)
        if file_id:
            print(f"Adding {filename} (ID: {file_id}) to KPS新聞...")
            if add_file_to_knowledge(file_id):
                print(f"Successfully processed: {filename}")
            else:
                print(f"Failed to add {filename} to knowledge base.")
        else:
            print(f"Failed to upload {filename}.")

if __name__ == "__main__":
    main()
