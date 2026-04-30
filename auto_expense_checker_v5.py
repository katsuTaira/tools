#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
【交通費申請 自動点検システム v3 (AI自律判定版)】

■ 概要
毎日決まった時間に経費申請システムから「交通費」の明細を抽出し、
AI（Gemini）がWeb検索を用いて運賃の妥当性を自動点検します。
2026年3月の運賃改定などの日付による価格変動もAIが自律的に判断します。

■ 運用設定
1. 送信先の設定:
   下方の「RECIPIENTS」変数に通知したいメールアドレスをカンマ区切りで入力してください。

2. APIキーの設定:
   Google AI Studioで発行したAPIキーを環境変数「GOOGLE_API_KEY」に設定してください。

3. 定期実行 (Cron) の設定例:
   毎日 8:30 に実行する場合 (crontab -e):
   30 8 * * * export GOOGLE_API_KEY="あなたのキー"; /home/taira/mypy/bin/python3 /home/taira/tools/auto_expense_checker_v3.py
"""

import subprocess
import json
import os
import re
import urllib.parse
from datetime import datetime
from google import genai
from google.genai import types

# --- 設定 ---
BASE_URL = "https://platform.kpscorp.jp/kpspl"
#BASE_URL = "http://localhost:8080/kpspl"
#BASE_URL = "https://y-officesc.kpscorp.jp/platform"
SEND_ACCOUNT = "katsusuke.taira@kpscorp.co.jp"
# 送信先アドレスを複数指定（カンマ区切り）
RECIPIENTS = "katsusuke.taira@kpscorp.co.jp, katsu.taira@gmail.com" 

# データの保存場所を固定
DATA_DIR = "/home/taira/tools/"
MASTER_FILE = os.path.join(DATA_DIR, "fare_master.json")
HISTORY_FILE = os.path.join(DATA_DIR, "processed_ids.json")
APP_CACHE_FILE = os.path.join(DATA_DIR, "app_cache.json")
#APP_CACHE_FILE = os.path.join(DATA_DIR, "app_cache_test.json")
BLACKLIST_FILE = os.path.join(DATA_DIR, "blacklist_ids.json")
#BLACKLIST_FILE = os.path.join(DATA_DIR, "blacklist_ids_test.json")
TRP_CACHE_FILE = os.path.join(DATA_DIR, "trp_cache.json")
#TRP_CACHE_FILE = os.path.join(DATA_DIR, "trp_cache_test.json")
REPORT_FILE = os.path.join(DATA_DIR, "daily_report.txt")
COOKIE_FILE = os.path.join(DATA_DIR, "cookies.txt")

# Gemini API設定 (環境変数 GOOGLE_API_KEY を使用)
API_KEY = os.environ.get("GOOGLE_API_KEY")

blacklist = {}

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

def verify_with_ai(route, date_val, amount, is_round, payee, content=""):
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
        prompt = f"""
        あなたは正確性を最重視する運賃の専門家であり、最新の運賃情報を常に把握しています。
        以下の交通運賃の妥当性を、webの情報を参考に利用日時点の正確な運賃（特に運賃改定情報を考慮して）で調査・判定してください。

        【調査対象】
        利用日: {date_val}
        区間: {route} (支払先: {payee})
        申請金額（片道相当）: {amount}円 
        補足情報 : {content}

        【判定プロセス】
        1. 最新の支払先の運賃改定情報を【参考：料金改定マスターデータ】を確認。
        2. 利用日({date_val})がどの改定日の適用期間に該当するかを判断。
        3. その時点での正確な運賃(IC優先)を特定。
        4. 申請金額と特定した運賃を比較し、一致したら「一致」、一致でなく20円以内なら「妥当」、それ以上なら「要確認」と判断。
        5. 根拠のない情報は含めないでください。必ず公式発表や信頼できるニュースソースに基づく情報を提供してください。
        6. 申請者は"{route} 乗換案内" というキーワードで検索して金額を申請してきているので、結果が要確認となった場合は、そのキーワードで検索した結果を吟味し、再度どちらが正しいかを判断してください。
                         
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
        grounding_tool = types.Tool(google_search=types.GoogleSearch())
        config = types.GenerateContentConfig(tools=[grounding_tool])
        response = client.models.generate_content(
            model="gemini-3-flash-preview", 
            contents=prompt,
            config=config
        )
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
    token = init()
    if not token:
        print("トークンの取得に失敗しました。")
        return
    doKeihi(token)
    doSyuchou(token)

def doKeihi(token):
    #print("経費申請を処理中...")
    if not os.path.exists(MASTER_FILE):
        with open(MASTER_FILE, "w") as f: json.dump({}, f)
    with open(MASTER_FILE, "r") as f: master = json.load(f)
    
    #processed_ids = []
    #if os.path.exists(HISTORY_FILE):
    #    with open(HISTORY_FILE, "r") as f: processed_ids = json.load(f)

    # 申請書キャッシュの読み込み
    app_cache = {}
    if os.path.exists(APP_CACHE_FILE):
        try:
            with open(APP_CACHE_FILE, "r") as f: app_cache = json.load(f)
        except:
            app_cache = {}

    data = fetch_json(f"{BASE_URL}/ad/Appform/table", token)
    app_table = next((t for t in data["tables"] if t.get("id") == "AppformTable"), None)
    target_apps = [row for row in app_table["rows"] if "2:申請中" in row["状態"] or "4:承認済" in row["状態"]]

    new_results = []
    master_updated = False
    blacklist_updated = False
    app_cache_updated = False

    for app in target_apps:
        app_no = app["申請書No."]["text"]
        last_updated = app.get("最終更新日", "")
        
        # 申請書単位のキャッシュチェック
        if app_no in app_cache and app_cache[app_no] == last_updated:
            continue

        detail_data = fetch_json(app["申請書No."]["url"], token)
        detail_table = next((t for t in detail_data["tables"] if t.get("id") == "AppdetailTable"), None)
        if not detail_table: 
            app_cache[app_no] = last_updated
            app_cache_updated = True
            continue
        update_detail_ok = True
        for row in detail_table["rows"]:
            update_row_ok = True
            amount_str = row.get("交通費", "¥0")
            if amount_str == "¥0": continue
            
            detail_url = row["日付"]["url"]
            row_detail = fetch_json(detail_url, token)
            row_fields = row_detail["forms"][0]["fields"]
            
            db_id = row_fields.get("id", {}).get("value") or f"{app_no}_{row['日付']['text']}_{row.get('from','')}_{row.get('to','')}_{amount_str}"

            if row_fields.get("AI判定") and row_fields["AI判定"].get("value") and row_fields["AI判定"]["value"] not in ["NG/Unknown", "Pending"]:
                continue
            
            if db_id in blacklist:
                print(f"Skipping blacklisted item ID: {db_id}")
                continue
            
            detail_id = f"{app_no}_{row['日付']['text']}_{row.get('from','')}_{row.get('to','')}_{amount_str}"
            route_key = f"{row.get('from','')}-{row.get('to','')}"
            date_val = row["日付"]["text"]
            raw_amt = int(amount_str.replace("¥","").replace(",",""))
            is_round = "往復" in row.get("内容", "")
            unit_price = raw_amt / 2 if is_round else raw_amt
            ai_correct = "N/A"
            
            print(f"AI調査中: {app_no} {date_val} {route_key}...")
            ai_res = verify_with_ai(route_key, date_val, unit_price, is_round, row.get("支払先名",""))
            if ai_res:
                thought, status, reason, last_rev = ai_res["thought"], ai_res["status"], ai_res["reason"], ai_res["last_revision_date"]
                ai_correct = ai_res["correct_fare"]
                if status == "要確認" and row_fields.get("AI判定", {}).get("value") != "Pending":
                    status = "Pending"

                print(f"POST送信中: {db_id} {ai_correct}-> {status}")
                post_url = f"{BASE_URL}/ad/Appdetail/sv"
                post_payload = {
                    f_info["name"]: f_info["value"] 
                    for f_name, f_info in row_fields.items() 
                    if isinstance(f_info, dict) and "name" in f_info and "value" in f_info
                }                   
                post_payload.update({"aijadge": status, "aifare": ai_correct, "aicomment": reason + "\n[算出根拠]:\n" + thought, "post": "true"})
                
                post_res = post_data_to_sv(post_url, token, post_payload)
                blacklist_updated = post_row_check(db_id, post_res)
            else:
                print(f"AI判定に失敗: {db_id}")
                update_row_ok = False
                update_detail_ok = False
            if update_row_ok:
                new_results.append({
                    "id": detail_id,
                    "text": f"| {app_no:<5} | {date_val:<10} | {app['申請者']['text']:<8} | {route_key:<20} | {unit_price:<6} | {ai_correct:<6} | {status:<10} | {reason} |"
                })
        if update_detail_ok:
            #processed_ids.append(detail_id)
            app_cache[app_no] = last_updated
            app_cache_updated = True

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if blacklist_updated:
        with open(BLACKLIST_FILE, "w", encoding="utf-8") as f:
            json.dump(blacklist, f, indent=2, ensure_ascii=False)
    if new_results or app_cache_updated:
        #with open(HISTORY_FILE, "w") as f: json.dump(processed_ids, f)
        if app_cache_updated:
            with open(APP_CACHE_FILE, "w", encoding="utf-8") as f: 
                json.dump(app_cache, f, indent=2, ensure_ascii=False)
        if new_results:
            print(f"{timestamp} 完了: {len(new_results)} 件の明細を更新しました。")
        else:
            print(f"{timestamp} 完了: キャッシュを更新しました。")
    #else:
        #print(f"{timestamp} 今回、新規明細はありません。")

def doSyuchou(token):
    trp_cache = {}
    trp_results = []
    blacklist_updated = False
    trp_cache_updated = False
    if os.path.exists(TRP_CACHE_FILE):
        try:
            with open(TRP_CACHE_FILE, "r") as f: trp_cache = json.load(f)
        except:
            trp_cache = {}
    #print("出張届及精算承認書を処理中...")
    trip_type_encoded = urllib.parse.quote("出張届及精算承認書")
    trip_data = fetch_json(f"{BASE_URL}/ad/adGenesheet/table?v={trip_type_encoded}", token)
    trip_table = next((t for t in trip_data["tables"] if t.get("id") == "GenesheetTable"), None)
    if trip_table:
        target_trips = [row for row in trip_table["rows"] if "2:申請中" in row["状態"] or "4:承認済" in row["状態"]]
        for trip in target_trips:
            app_no = trip["申請書No."]["text"]
            last_updated = trip.get("更新日", "")
            if app_no in trp_cache and trp_cache[app_no] == last_updated:
                continue

            detail_data = fetch_json(trip["申請書No."]["url"], token)
            row_fields = detail_data["forms"][0]["fields"]
            
            # scriptVarsからparamsを取得
            script_vars = detail_data["forms"][0].get("scriptVars", [])
            if not script_vars: continue
            # シングルクォートをダブルクォートに置換して JSON としてパース
            params_str = script_vars[0]["params"].replace("'", '"')
            params_obj = json.loads(params_str)

            # itemTableJsonToTableTable 内の運賃をチェック
            item_table = next((t for t in detail_data["tables"] if t.get("id") == "itemTableJsonToTableTable"), None)
            if not item_table:
                trp_cache[app_no] = last_updated
                trp_cache_updated = True
                continue
            update_detail_ok = True
            for row in item_table["rows"]:
                update_row_ok = True
                if "運賃" not in row.get("項目", {}).get("text", ""):
                    continue
                if row.get("AI判定") and row["AI判定"] not in ["NG/Unknown", "Pending"]:
                    continue
                data_ix = row.get("項目", {}).get("data-ix")
                if not data_ix: continue

                db_id = f"trip_{app_no}_{data_ix}"
                if db_id in blacklist:
                    print(f"Skipping blacklisted item ID: {db_id}")
                    continue

                # 明細の詳細をPOSTで取得
                params_for_detail = params_obj.copy()
                params_for_detail["rowId"] = data_ix
                post_payload = {
                    f_info["name"]: f_info["value"] 
                    for f_name, f_info in row_fields.items() 
                    if isinstance(f_info, dict) and "name" in f_info and "value" in f_info
                }
                post_payload.update({"itemTableParams": json.dumps(params_for_detail), "head": "itemTable"})
                item_detail_res = post_data_to_sv(f"{BASE_URL}/ad/itemTable/edit", token, post_payload)
                item_detail = json.loads(item_detail_res)
                item_fields = item_detail["forms"][0]["fields"]
 
                # 運賃情報の抽出 (itemTableのフィールド名に合わせる)
                date_val = item_fields.get("月／日", {}).get("value", "")
                from_st = item_fields.get("駅from", {}).get("value", "")
                to_st = item_fields.get("駅to", {}).get("value", "")
                amount_val = item_fields.get("金額", {}).get("value", "0")
                payee = item_fields.get("支払先名", {}).get("value", "")
                content = item_fields.get("項目", {}).get("value", "")
                
                if not date_val or amount_val == "0": continue
                
                route_key = f"{from_st}-{to_st}"
                raw_amt = int(str(amount_val).replace(",",""))
                #is_round = "往復" in content
                #unit_price = raw_amt / 2 if is_round else raw_amt
                is_round = False  # 出張届の運賃は基本的に片道で申請される想定のため、往復判定は行わない
                unit_price = raw_amt

                print(f"AI調査中 (Trip): {app_no} {date_val} {route_key}...")
                ai_res = verify_with_ai(route_key, date_val, unit_price, is_round, payee, content)
                if ai_res:
                    thought, status, reason, last_rev = ai_res["thought"], ai_res["status"], ai_res["reason"], ai_res["last_revision_date"]
                    ai_correct = ai_res["correct_fare"]
                    if status == "要確認" and item_fields.get("AI判定", {}).get("value") != "Pending":
                        status = "Pending"
                    print(f"POST送信中: {db_id} {ai_correct}-> {status}")
                    post_payload = {
                        f_info["name"]: f_info["value"] 
                        for f_name, f_info in item_fields.items() 
                        if isinstance(f_info, dict) and "name" in f_info and "value" in f_info
                    }                   
                    post_payload.update({"aijadge": status, "aifare": ai_correct, "aicomment": reason + "\n[算出根拠]:\n" + thought, "post": "true"})
                    post_payload.update({"itemTableParams": json.dumps(params_for_detail), "head": "itemTable"})
                    # 保存先URLは経費精算と同じパターンと仮定
                    post_res = post_data_to_sv(f"{BASE_URL}/ad/itemTable/sv", token, post_payload)
                    blacklist_updated = post_row_check(db_id, post_res)
                else:
                    print(f"AI判定に失敗: {db_id}")
                    update_row_ok = False
                    update_detail_ok = False
                if update_row_ok:
                    trp_results.append({"id": db_id, "text": f"| {app_no:<5} | {date_val:<10} | {trip['申請者']['text']:<8} | {route_key:<20} | {unit_price:<6} | {ai_correct:<6} | {status:<10} | {reason} |"})
            if update_detail_ok:
                trp_cache[app_no] = last_updated
                trp_cache_updated = True 
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if blacklist_updated:
        with open(BLACKLIST_FILE, "w", encoding="utf-8") as f:
            json.dump(blacklist, f, indent=2, ensure_ascii=False)
    if trp_results or trp_cache_updated:
        if trp_cache_updated:
            with open(TRP_CACHE_FILE, "w", encoding="utf-8") as f: json.dump(trp_cache, f, indent=2, ensure_ascii=False)
        if trp_results:
            print(f"{timestamp} 完了: {len(trp_results)} 件の出張明細を更新しました。")
        else:
            print(f"{timestamp} 完了: 出張キャッシュを更新しました。")
    #else:
        #print(f"{timestamp} 今回、新規出張明細はありません。")

def post_row_check(db_id, post_res):
    blacklist_updated = False
    try:
        res_json = json.loads(post_res)
        if any(isinstance(m, dict) and m.get("type") == "error" for m in res_json.get("messages", [])):
                            # POSTエラー時の処理                            
            fields = res_json["forms"][0]["fields"]
                            # fieldsの中で error がるものを探す
            error_keys = [k for k,v in fields.items() if isinstance(v, dict) and v.get("error")]
            error_detail =  f"{error_keys[0]} : {fields[error_keys[0]].get('error')}"
            blacklist[db_id] = error_detail
            blacklist_updated = True
            print(f"POSTでエラー発生 {db_id}: {error_detail}")
            update_row_ok = False
            update_detail_ok = False
    except Exception as e:
        print(f"Warning: Could not parse POST response: {e}")
    return blacklist_updated

def init():
    if not API_KEY:
        print("GOOGLE_API_KEY is not set.")
        return

    if os.path.exists(COOKIE_FILE):
        os.remove(COOKIE_FILE)

    token = get_token()
    
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
    global blacklist
    blacklist = {}
    if os.path.exists(BLACKLIST_FILE):
        with open(BLACKLIST_FILE, "r") as f: blacklist = json.load(f)

    return token

if __name__ == "__main__":
    main()
