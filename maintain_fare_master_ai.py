import json
import os
import re
from datetime import datetime

# --- 設定 ---
MASTER_FILE = '/home/taira/tools/fare_revision_master.json'
# Gemini API設定 (環境変数 GOOGLE_API_KEY を使用)
API_KEY = os.environ.get("GOOGLE_API_KEY")

def update_master_with_ai():
    """Gemini APIを使用して運賃改定情報を検索し、マスタを更新する"""
    if not API_KEY:
        print("Error: GOOGLE_API_KEY is not set.")
        return

    try:
        import google.generativeai as genai
    except ImportError:
        print("Error: google-generativeai library is not installed.")
        print("Please run: pip install google-generativeai")
        return

    genai.configure(api_key=API_KEY)
    
    # 2026年3月のJR東日本の改定など、具体的なターゲットを含めて検索
    model = genai.GenerativeModel('gemini-3-flash-preview')
    
    prompt = """
    日本の鉄道会社およびバス会社の運賃改定日（特に2025年、2026年の予定）を調査してください。
    
    以下の条件で情報を抽出してください：
    1. 会社名と、その会社が実施した（または予定している）運賃改定日のリスト。
    2. 日付は YYYY/MM/DD の形式に統一してください。
    3. 2024年以前の情報も含めて構いませんが、最新の予定（2026/03/14など）を優先してください。
    
    回答は必ず以下の純粋なJSON形式のみで出力してください（Markdownの装飾は不要です）:
    {
      "会社名": ["YYYY/MM/DD", "YYYY/MM/DD"],
      ...
    }
    """

    print("Searching for latest fare revision info using Gemini AI...")
    try:
        response = model.generate_content(prompt)
        # JSON部分を抽出
        json_text = response.text
        match = re.search(r'\{.*\}', json_text, re.DOTALL)
        if not match:
            print("Failed to parse JSON from AI response.")
            print("Response:", json_text)
            return

        new_data = json.loads(match.group())
        print(f"AI found info for {len(new_data)} companies.")
        
        merge_and_save(new_data)
    except Exception as e:
        print(f"An error occurred: {e}")

def merge_and_save(new_data):
    """取得したデータを既存のマスタにマージする"""
    if os.path.exists(MASTER_FILE):
        with open(MASTER_FILE, 'r', encoding='utf-8') as f:
            master = json.load(f)
    else:
        master = {}

    updated_count = 0
    new_companies = 0

    for company, dates in new_data.items():
        if company not in master:
            master[company] = sorted(list(set(dates)), reverse=True)
            new_companies += 1
            updated_count += len(dates)
        else:
            existing_dates = set(master[company])
            added = False
            for d in dates:
                if d not in existing_dates:
                    master[company].append(d)
                    added = True
                    updated_count += 1
            if added:
                master[company] = sorted(list(set(master[company])), reverse=True)

    with open(MASTER_FILE, 'w', encoding='utf-8') as f:
        json.dump(master, f, ensure_ascii=False, indent=2)
    
    print(f"Update complete. Total companies: {len(master)}")
    print(f"New companies added: {new_companies}, New dates added: {updated_count}")

if __name__ == '__main__':
    update_master_with_ai()
