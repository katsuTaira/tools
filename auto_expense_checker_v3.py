#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
【交通費申請 自動点検システム v3 (AI自律判定版)】

■ 概要
毎日決まった時間に経費申請システムから「交通費」の明細を抽出し、
AI（Gemini）がWeb検索を用いて運賃の妥当性を自動点検します。
2026年3月の運賃改定などの日付による価格変動もAIが自律的に判断します。
from google import genai
from google.genai.types import Tool, GoogleSearch

■ 運用設定
1. 送信先の設定:
   下方の「RECIPIENTS」変数に通知したいメールアドレスをカンマ区切りで入力してください。

2. APIキーの設定:
   Google AI Studioで発行したAPIキーを環境変数「GOOGLE_API_KEY」に設定してください。

3. 定期実行 (Cron) の設定例:
   毎日 8:30 に実行する場合 (crontab -e):
   30 8 * * * export GOOGLE_API_KEY="あなたのキー"; /home/taira/mypy/bin/python3 /home/taira/tools/auto_expense_checker_v3.py
■ ディレクトリ構造
/home/taira/tools/
├── auto_expense_checker_v3.py  (このスクリプト)
├── fare_revision_master.json   (料金改定マスターデータ)



"""

import subprocess
import json
import os
import re
from datetime import datetime
#import google.generativeai as genai
from google import genai

# --- 設定 ---
#BASE_URL = "https://platform.kpscorp.jp/kpspl"!pip install -Uqq google-generativeai
#BASE_URL = "http://localhost:8080/kpspl"
BASE_URL = "https://y-officesc.kpscorp.jp/platform"
SEND_ACCOUNT = "katsusuke.taira@kpscorp.co.jp"
# 送信先アドレスを複数指定（カンマ区切り）
RECIPIENTS = "katsusuke.taira@kpscorp.co.jp, katsu.taira@gmail.com" 

# データの保存場所を固定
DATA_DIR = "/home/taira/tools/"
MASTER_FILE = os.path.join(DATA_DIR, "fare_master.json")
HISTORY_FILE = os.path.join(DATA_DIR, "processed_ids.json")
BLACKLIST_FILE = os.path.join(DATA_DIR, "blacklist_ids.json")
REPORT_FILE = os.path.join(DATA_DIR, "daily_report.txt")
COOKIE_FILE = os.path.join(DATA_DIR, "cookies.txt")

# Gemini API設定 (環境変数 GOOGLE_API_KEY を使用)
API_KEY = os.environ.get("GOOGLE_API_KEY")

def get_token():
    return subprocess.check_output(["gcloud", "auth", "print-identity-token"]).decode("utf-8").strip()

def fetch_json(url, token):
    if "format=json" not in url:
        url += ("&" if "?" in url else "?") + "format=json"
    # クッキーの読み込み(-b)と保存(-c)を追加
    cmd = [
        "curl", "-s", 
        "-b", COOKIE_FILE, 
        "-c", COOKIE_FILE, 
        "-H", f"Authorization: Bearer {token}", 
        url
    ]
    result = subprocess.check_output(cmd)
    return json.loads(result)

def post_data_to_sv(url, token, data):
    if "format=json" not in url:
        url += ("&" if "?" in url else "?") + "format=json"

    # gcloud auth print-identity-token を使用した認証
    headers = [f"Authorization: Bearer {token}"]
    
    # post data の構築
    post_args = []
    for k, v in data.items():
        post_args.append("-d")
        post_args.append(f"{k}={v}")
    
    # クッキーの読み込み(-b)と保存(-c)を追加
    cmd = [
        "curl", "-s", "-X", "POST",
        "-b", COOKIE_FILE,
        "-c", COOKIE_FILE
    ]
    for h in headers:
        cmd.extend(["-H", h])
    cmd.extend(post_args)
    cmd.append(url)
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.stdout

def verify_with_ai(route, date_val, amount, is_round, payee):
    """AIが日付から運賃改定を自己検索して判定する"""
    if not API_KEY:
        return {"status": "Error", "reason": "API_KEY未設定"}
        
    # 料金改定マスタの読み込み
    revision_master_path = '/home/taira/tools/fare_revision_master.json'
    revision_info = ""
    if os.path.exists(revision_master_path):
        try:
            with open(revision_master_path, 'r', encoding='utf-8') as f:
                revision_data = json.load(f)
                revision_info = json.dumps(revision_data, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"料金改定マスタの読み込みに失敗しました: {e}")

    try:
        #genai.configure(api_key=API_KEY)
        #model = genai.GenerativeModel('gemini-3.1-pro-preview') 
        #model = genai.GenerativeModel('gemini-3-flash-preview')       
        prompt = f"""
        あなたは正確性を最重視する運賃の専門家であり、最新の運賃情報を常に把握しています。
        以下の交通運賃の妥当性を、webの情報を参考に利用日時点の正確な運賃（特に運賃改定情報を考慮して）で調査・判定してください。

        【調査対象】
        利用日: {date_val}
        区間: {route} (支払先: {payee})
        申請金額（片道相当）: {amount}円 

        【判定プロセス】
        1. 最新の支払先の運賃改定情報を【参考：料金改定マスターデータ】を基にを検索。
        2. 利用日({date_val})がどの改定日の適用期間に該当するかを判断。
        3. その時点での正確な運賃(IC優先)を特定。
        4. 申請金額と特定した運賃を比較し、一致したら「一致」、一致でなく20円以内なら「妥当」、それ以上なら「要確認」と判断。
        5. 根拠のない情報は含めないでください。必ず公式発表や信頼できるニュースソースに基づく情報を提供してください。
    
        【参考：料金改定マスターデータ】
        以下の情報は、各社の過去および予定されている料金改定日です。判定の参考にしてください。
        {revision_info}

        【回答形式】
        必ず以下のJSON形式のみで回答してください（説明不要）:
        {{
          "thought": "判断の根拠を順番に記述（100字以内）",
          "status": "一致" または "妥当" または "要確認",
          "reason": "具体的な判断根拠",
          "correct_fare": 数値(特定した片道運賃),
          "last_revision_date": "適用した最後の改定日(YYYY/MM/DD)"
        }}
        """
        client = genai.Client()
        response = client.models.generate_content(model="gemini-3-flash-preview", contents=prompt)
        #response = client.models.generate_content(model="gemini-3.1-pro-preview", contents=prompt)
        
        # JSON部分を抽出
        text = response.text
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            return json.loads(match.group())
        else:
            print(f"AIからの応答にJSONが含まれていません: {text}")
            return None
    except Exception as e:
        print(f"AI判定中にエラーが発生しました ({route}): {e}")
        return None

def main():
    if not API_KEY:
        print("GOOGLE_API_KEY is not set.")
        return

    # 実行ごとにクッキーをリセットして古いセッションを破棄
    if os.path.exists(COOKIE_FILE):
        os.remove(COOKIE_FILE)

    token = get_token()
    
    # ディレクトリ作成
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
        
    if not os.path.exists(MASTER_FILE):
        with open(MASTER_FILE, "w") as f: json.dump({}, f)
    with open(MASTER_FILE, "r") as f: master = json.load(f)
    
    # 履歴ファイルはバックアップとして残すが、基本は aijadge でチェック
    processed_ids = []
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r") as f: processed_ids = json.load(f)

    # ブラックリスト（エラーにより修正が必要な明細）の読み込み
    blacklist = []
    if os.path.exists(BLACKLIST_FILE):
        with open(BLACKLIST_FILE, "r") as f: blacklist = json.load(f)

    data = fetch_json(f"{BASE_URL}/ad/Appform/table", token)
    app_table = next((t for t in data["tables"] if t.get("id") == "AppformTable"), None)
    target_apps = [row for row in app_table["rows"] if "2:申請中" in row["状態"] or "4:承認済" in row["状態"]]

    new_results = []
    master_updated = False
    blacklist_updated = False

    for app in target_apps:
        app_no = app["申請書No."]["text"]
        detail_data = fetch_json(app["申請書No."]["url"], token)
        detail_table = next((t for t in detail_data["tables"] if t.get("id") == "AppdetailTable"), None)
        if not detail_table: continue

        for row in detail_table["rows"]:
            amount_str = row.get("交通費", "¥0")
            if amount_str == "¥0": continue
            
            detail_url = row["日付"]["url"]
            # 明細詳細情報を取得して aijadge をチェック
            row_detail = fetch_json(detail_url, token)
            row_fields = row_detail["forms"][0]["fields"]
            
            # DB上のIDを取得
            db_id = row_fields.get("id", {}).get("value")
            if not db_id:
                # 万が一取れない場合は従来の形式をフォールバックとして使用
                db_id = f"{app_no}_{row['日付']['text']}_{row.get('from','')}_{row.get('to','')}_{amount_str}"

            # 157行目付近: 作業済みチェック (aijadgeがあるか)
            if row_fields.get("AI判定") and row_fields["AI判定"].get("value"):
                continue
          
            # ブラックリストに入っている場合はスキップ
            if db_id in blacklist:
                print(f"Skipping blacklisted item ID: {db_id}")
                continue
            
            detail_id = f"{app_no}_{row['日付']['text']}_{row.get('from','')}_{row.get('to','')}_{amount_str}"
            
            # このチェックはしない     
         #   if detail_id in processed_ids: continue

            route_key = f"{row.get('from','')}-{row.get('to','')}"
            date_val = row["日付"]["text"]
            raw_amt = int(amount_str.replace("¥","").replace(",",""))
            is_round = "往復" in row.get("内容", "")
            unit_price = raw_amt / 2 if is_round else raw_amt
            ai_correct = "N/A"
            expected = -1
            status, reason = "NG/Unknown", "AI判定失敗"
            
            # 常にAI調査を行うため、既存のマスタールックアップをスキップ
            """
            if route_key in master:
                # ... (既存のルックアップ処理)
            """
            
            print(f"AI調査中: {date_val} {route_key}...")
            ai_res = verify_with_ai(route_key, date_val, unit_price, is_round, row.get("支払先名",""))
            if ai_res:
                status, reason, last_revision_date = ai_res["status"], ai_res["reason"], ai_res["last_revision_date"]
                if route_key not in master: master[route_key] = {}
                master[route_key][last_revision_date] = {
                    "ai_correct": ai_res["correct_fare"],
                    "reason": reason
                }
                ai_correct = ai_res["correct_fare"]
                master_updated = True
            else:
                status, reason = "NG/Unknown", "AI判定失敗"

            # 193行目付近: POST処理
            print(f"POST送信中: {detail_id} -> {status}")
            post_url = f"{BASE_URL}/ad/Appdetail/sv"
            post_payload = {}
            # detailで入手した全フィールドを設定
            for f_name, f_info in row_fields.items():
                if isinstance(f_info, dict) and "name" in f_info:
                    post_payload[f_info["name"]] = f_info["value"]
            
            # 指定されたフィールドを上書き・追加
            post_payload["aijadge"] = status
            post_payload["aifare"] = ai_correct
            post_payload["aicomment"] = reason
            post_payload["post"] = "true"
            
            post_res = post_data_to_sv(post_url, token, post_payload)
            
            # レスポンスのチェック: エラーがあればブラックリストに追加
            try:
                res_json = json.loads(post_res)
                if any(m.get("type") == "error" for m in res_json.get("messages", [])):
                    error_details = []
                    # フィールドごとのエラーを抽出
                    for form in res_json.get("forms", []):
                        for f_key, f_val in form.get("fields", {}).items():
                            if isinstance(f_val, dict) and "error" in f_val:
                                err_msg = f"[{f_key}] {f_val['error']}"
                                error_details.append(err_msg)
                    
                    error_summary = ", ".join(error_details) if error_details else "不明な入力エラー"
                    print(f"ERROR returned from server for ID {db_id}: {error_summary}")
                    
                    if db_id not in blacklist:
                        blacklist.append(db_id)
                        blacklist_updated = True
                    continue # 次の明細へ
            except Exception as e:
                print(f"Warning: Could not parse POST response: {e}")
            
            new_results.append({
                "id": detail_id,
                "text": f"| {app_no:<5} | {date_val:<10} | {app['申請者']['text']:<8} | {route_key:<20} | {unit_price:<6} | {ai_correct:<6} | {status:<10} | {reason} |"
            })
            processed_ids.append(detail_id)

    if new_results:
        # 履歴とマスターの更新のみ行う
        with open(HISTORY_FILE, "w") as f: json.dump(processed_ids, f)
        if master_updated:
            with open(MASTER_FILE, "w", encoding="utf-8") as f: 
                json.dump(master, f, indent=2, ensure_ascii=False)
        if blacklist_updated:
            with open(BLACKLIST_FILE, "w", encoding="utf-8") as f:
                json.dump(blacklist, f, indent=2, ensure_ascii=False)
        print(f"完了: {len(new_results)} 件の明細を更新しました。")
    else:
        print("本日の新規明細はありません。")

if __name__ == "__main__":
    main()


