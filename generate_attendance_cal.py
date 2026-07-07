#!/usr/bin/env python3
import subprocess
import json
import os
import sys
from datetime import datetime, timedelta
import pytz
from icalendar import Calendar, Event

# --- 設定 ---
GOG_PATH = "/home/linuxbrew/.linuxbrew/bin/gog"
ACCOUNT = "katsusuke.taira@kpscorp.co.jp"
# OneDriveのパス (環境に合わせて /mnt/c/Users/taira/ を使用)
OUTPUT_PATH = "/mnt/c/Users/taira/OneDrive/ドキュメント/attendance.ics"
SCP_DESTINATION = "SWT:/a0/var/pub/video/"

def get_timestamp():
    """現在時刻のタイムスタンプ文字列を返す"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def run_gog(args):
    # cron環境向けに空のパスワードを明示的にセット
    env = os.environ.copy()
    env["GOG_KEYRING_PASSWORD"] = ""
    
    # すべてのコマンドにアカウント指定を追加
    cmd = [GOG_PATH, "-a", ACCOUNT] + args
    result = subprocess.run(cmd, capture_output=True, text=True, env=env)
    if result.returncode != 0:
        print(f"{get_timestamp()} Error running gog {' '.join(args[:2])}: {result.stderr.strip()}")
        return None
    return result.stdout

def get_calendar_events(days=30):
    """指定された日数分のカレンダーイベントを取得"""
    res = run_gog(["calendar", "events", "--days", str(days), "-j", "--results-only"])
    return json.loads(res) if res else []

def is_google_meet(event):
    """Google Meetの予定であるかを判定。
    ただし、予定に会議室（リソース）が含まれており、自身が参加（accepted）となっている場合は
    対面での会議室参加とみなして Google Meet 扱い（除外）から除きます。
    """
    has_meet = False
    # Hangout link indicates a Meet; check URL for meet.google.com
    if "hangoutLink" in event:
        link = event.get("hangoutLink", "").lower()
        if "meet.google.com" in link:
            has_meet = True
        else:
            has_meet = True
    elif "conferenceData" in event:
        has_meet = True
    else:
        summary = event.get("summary", "").lower()
        location = event.get("location", "").lower()
        description = event.get("description", "").lower()
        if "google meet" in summary or "google meet" in location or "google meet" in description:
            has_meet = True
            
    if not has_meet:
        return False
        
    # 会議に「会議室（resource: True）」が承諾（accepted）で含まれており、
    # かつ自分（self: True）が参加承諾（accepted）しているかを確認
    attendees = event.get("attendees", [])
    has_room_accepted = any(att.get("resource") is True and att.get("responseStatus") == "accepted" for att in attendees)
    self_accepted = any(att.get("self") is True and att.get("responseStatus") == "accepted" for att in attendees)
    
    if has_room_accepted and self_accepted:
        # 会議室で参加すると判断し、Google Meet判定（除外）から外す
        return False
        
    return True

def generate_attendance_ics(events, output_path):
    cal = Calendar()
    cal.add("prodid", "-//KPS Attendance Calendar Generator//")
    cal.add("version", "2.0")
    cal.add("X-WR-CALNAME", "出勤カレンダー")
    cal.add("X-WR-TIMEZONE", "Asia/Tokyo")
    
    jst = pytz.timezone("Asia/Tokyo")
    candidates_by_date = {}
    
    for event in events:
        # Google Meet の予定は除外（会議室で対面参加する場合は除外しない）
        if is_google_meet(event):
            continue
            
        start_info = event.get("start", {})
        if not start_info or "dateTime" not in start_info:
            # 終日イベントなどはスキップ
            continue
            
        dt_str = start_info["dateTime"]
        try:
            dt = datetime.fromisoformat(dt_str)
        except Exception as e:
            print(f"{get_timestamp()} Error parsing date {dt_str}: {e}")
            continue
            
        # Asia/Tokyoタイムゾーンに変換
        dt_jst = dt.astimezone(jst)
        date_str = dt_jst.strftime("%Y-%m-%d")
        
        # 午前の予定（開始が12:00未満）の場合はその時間の1時間15分前
        # 午後の予定（開始が12:00以降）の場合は固定で 11:20
        limit_noon = dt_jst.replace(hour=12, minute=0, second=0, microsecond=0)
        
        if dt_jst < limit_noon:
            attendance_time = dt_jst - timedelta(hours=1, minutes=15)
        else:
            attendance_time = dt_jst.replace(hour=11, minute=20, second=0, microsecond=0)
            
        if date_str not in candidates_by_date:
            candidates_by_date[date_str] = []
        candidates_by_date[date_str].append(attendance_time)
        
    # 各日付で最も早い出勤時刻を採用
    for date_str, times in sorted(candidates_by_date.items()):
        earliest_time = min(times)
        
        event = Event()
        event.add("summary", "出勤")
        event.add("dtstart", earliest_time)
        event.add("dtend", earliest_time) # 開始・終了同じ時刻
        
        # 重複判定用のユニークID
        event.add("uid", f"attendance-{date_str}@kpscorp.co.jp")
        event.add("dtstamp", datetime.now(pytz.utc))
        
        cal.add_component(event)

    # ディレクトリがなければ作成
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    with open(output_path, "wb") as f:
        f.write(cal.to_ical())
    print(f"{get_timestamp()} iCalendarファイルを保存しました: {output_path}")

def transfer_via_scp(file_path, destination):
    """生成したicsファイルをscpで転送"""
    print(f"{get_timestamp()} SCPでファイルを転送中: {file_path} -> {destination}")
    cmd = ["scp", file_path, destination]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"{get_timestamp()} SCP転送エラー: {result.stderr.strip()}")
    else:
        print(f"{get_timestamp()} SCP転送が完了しました。")

def main():
    print(f"{get_timestamp()} Googleカレンダーから予定を取得中...")
    events = get_calendar_events(days=30)  # 直近30日分
    if not events:
        print(f"{get_timestamp()} イベントが取得できませんでした、または予定がありません。")
        return
        
    print(f"{get_timestamp()} {len(events)} 件の予定から出勤時間を計算中...")
    generate_attendance_ics(events, OUTPUT_PATH)
    
    # SCPで転送を実行
    if os.path.exists(OUTPUT_PATH):
        transfer_via_scp(OUTPUT_PATH, SCP_DESTINATION)

if __name__ == "__main__":
    main()