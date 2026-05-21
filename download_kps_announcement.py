#!/usr/bin/env python3
import subprocess
import json
import os
import sys
from datetime import datetime

# --- 設定 ---
GOG_PATH = "/home/linuxbrew/.linuxbrew/bin/gog"
DOWNLOAD_DIR = "/mnt/c/Users/K00013/OneDrive/ドキュメント/メールダウンロード"
SUBJECT_MAINS = ("[G Suite for KPS] 発令", "[G Suite for KPS] 回覧")
SUBJECT_SUB = "[G Suite for KPS] おしらせ"
ACCOUNT = "katsusuke.taira@kpscorp.co.jp"

def run_gog(args):
    # cron環境向けに空のパスワードを明示的にセット
    env = os.environ.copy()
    env["GOG_KEYRING_PASSWORD"] = ""
    
    # すべてのコマンドにアカウント指定を追加
    cmd = [GOG_PATH, "-a", ACCOUNT] + args
    result = subprocess.run(cmd, capture_output=True, text=True, env=env)
    if result.returncode != 0:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"{timestamp} Error running gog {' '.join(args[:2])}: {result.stderr.strip()}")
        return None
    return result.stdout

def set_file_mtime(file_path, date_str):
    """ファイルの最終更新日時を指定された文字列(YYYY-MM-DD HH:MM)に合わせる"""
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d %H:%M")
        ts = dt.timestamp()
        os.utime(file_path, (ts, ts))
    except Exception as e:
        print(f"  Error setting mtime for {file_path}: {e}")

def get_messages(query):
    """検索クエリに合致するメッセージ一覧を取得"""
    res = run_gog(["gmail", "search", query, "--json", "--results-only", "--max", "20"])
    return json.loads(res) if res else []

def download_attachments(message_id, dest_dir, msg_date):
    """メッセージの添付ファイルをダウンロードし、保存したファイル名のリストを返す"""
    res = run_gog(["gmail", "get", message_id, "--json"])
    if not res: return []
    
    msg_detail = json.loads(res)
    downloaded_files = []
    
    # 実際のJSON構造に合わせてキー名を修正 (attachments -> attachmentId, filename)
    attachments = msg_detail.get("attachments", [])
    if not attachments:
        return []

    for att in attachments:
        att_id = att.get("attachmentId")
        filename = att.get("filename")
        if not att_id or not filename: continue
        
        target_path = os.path.join(dest_dir, filename)
        if os.path.exists(target_path):
            print(f"  File already exists: {filename}")
            return None # 既存のためこのメールはスキップ
            
        print(f"  Downloading: {filename}...")
        # gog gmail attachment <msgId> <attId> --output <path>
        run_gog(["gmail", "attachment", message_id, att_id, "--output", target_path])
        # 更新日時をセット
        set_file_mtime(target_path, msg_date)
        downloaded_files.append(filename)
        
    return downloaded_files

def save_next_announcement_body(filename, base_date):
    """指定された日付以降の「おしらせ」メールの中で、最も日時の近い（直後の）1件を取得して保存"""
    # base_date は "2026-05-01 10:39" のような形式。
    # 同日のものも含めるため、時間を考慮せず日付だけで検索
    date_query = base_date.split(" ")[0].replace("-", "/")
    query = f'subject:"{SUBJECT_SUB}" after:{date_query}'
    
    announcements = get_messages(query)
    if not announcements:
        print(f"  No related announcement found for {filename}")
        return

    # メッセージを日付の昇順（古い順）にソートして、base_date直後のものを探す
    # announcements[i]["date"] は "2026-05-01 10:39" 形式
    announcements.sort(key=lambda x: x["date"])
    
    target_ann = None
    for ann in announcements:
        if ann["date"] >= base_date:
            target_ann = ann
            break
            
    if not target_ann:
        print(f"  No announcement found after {base_date} for {filename}")
        return

    ann_id = target_ann["id"]
    print(f"  Getting announcement body (closest after {base_date}) from: {ann_id}")
    # 本文を取得 (--plain)
    body = run_gog(["gmail", "get", ann_id, "--plain"])
    
    if body:
        txt_path = os.path.join(DOWNLOAD_DIR, f"{filename}.txt")
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(body)
        # 更新日時をセット
        set_file_mtime(txt_path, target_ann["date"])
        print(f"  Saved announcement body to: {filename}.txt")

def main():
    if not os.path.exists(DOWNLOAD_DIR):
        os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
   
    for subject in SUBJECT_MAINS:
        main_emails = []
        print(f"{timestamp} Searching for emails with subject: {subject}")
        main_emails.extend(get_messages(f'subject:"{subject}"'))
        for msg in main_emails:
            msg_id = msg["id"]
            msg_date = msg["date"] 
            print(f"Checking email ID: {msg_id} ({msg_date})")
            # 2026以降のメールのみ処理
            if int(msg_date[:4]) < 2026:
                print("  Skipping (not from 2026 or later).")
                break
            
            # 添付ファイルのダウンロード試行
            downloaded = download_attachments(msg_id, DOWNLOAD_DIR, msg_date)
            
            if downloaded is None:
                # すでにダウンロード済みのファイル名だった場合
                continue
            
            if downloaded:
                for fname in downloaded:
                    save_next_announcement_body(fname, msg_date)
                # 最新の1通を処理したら終了
                break
            else:
                print("  No attachments found in this email.")

if __name__ == "__main__":
    main()
