#!/usr/bin/env python3
import subprocess
import json
import os
from datetime import datetime, timezone

# --- 設定 ---
FOLDER_ID = "15foXxqFV0wGRDxtBw0jbmHNmuxAl2uTq"
LOCAL_DIR = "/mnt/c/Users/K00013/OneDrive/ドキュメント/qa_poc_light/就業規則"
ACCOUNT = "katsusuke.taira@kpscorp.co.jp"
# --- --- ---

def get_drive_files():
    """Drive上のファイル一覧を取得"""
    cmd = ["gog", "ls", "--parent", FOLDER_ID, "--json", "--max", "100", "--results-only"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error listing files: {result.stderr}")
        return []
    return json.loads(result.stdout)

def download_file(file_id, output_path):
    """ファイルをダウンロード"""
    cmd = ["gog", "download", file_id, "--output", output_path]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode == 0

def send_notification(downloaded_files):
    """メール送信"""
    subject = "【自動通知】就業規則フォルダが更新されました"
    body = "以下のファイルが新しくダウンロードされました：\n\n" + "\n".join(downloaded_files)
    cmd = ["gog", "send", "-a", ACCOUNT, "--to", ACCOUNT, "--subject", subject, "--body", body]
    subprocess.run(cmd)

def main():
    if not os.path.exists(LOCAL_DIR):
        print(f"Local directory not found: {LOCAL_DIR}")
        return

    drive_files = get_drive_files()
    downloaded_names = []

    for df in drive_files:
        file_name = df["name"]
        file_id = df["id"]
        # Driveの時刻をパース (ISO 8601)
        # modifiedTime: 2025-11-27T07:43:23.000Z
        drive_time = datetime.fromisoformat(df["modifiedTime"].replace("Z", "+00:00"))
        
        local_path = os.path.join(LOCAL_DIR, file_name)
        
        should_download = False
        if not os.path.exists(local_path):
            print(f"New file found: {file_name}")
            should_download = True
        else:
            # ローカルの更新日時 (タイムスタンプをUTCのdatetimeオブジェクトに変換)
            local_time = datetime.fromtimestamp(os.path.getmtime(local_path), tz=timezone.utc)
            # Drive側が新しいかチェック (秒単位での比較)
            if drive_time > local_time:
                print(f"Updated file found: {file_name} (Drive: {drive_time}, Local: {local_time})")
                should_download = True

        if should_download:
            if download_file(file_id, local_path):
                print(f"Successfully downloaded: {file_name}")
                downloaded_names.append(file_name)
            else:
                print(f"Failed to download: {file_name}")

    if downloaded_names:
        print(f"Sending notification for {len(downloaded_names)} files...")
        send_notification(downloaded_names)
    else:
        print("No updates found.")

if __name__ == "__main__":
    main()
