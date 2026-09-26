import asyncio
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
import os
import threading
import time
import pytz
import requests
import schedule

# --- RENDER HEALTH CHECK SERVER ---
class HealthCheck(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(b"OK")

    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()

    def log_message(self, format, *args):
        return

def run_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), HealthCheck)
    server.serve_forever()

threading.Thread(target=run_server, daemon=True).start()

# --- CONFIGURATION ---
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
CHAT_ID = os.environ.get("CHAT_ID", "")
EMAIL = os.environ.get("QUOTEX_EMAIL", "quotexmcandlereport@gmail.com")
PASSWORD = os.environ.get("QUOTEX_PASSWORD", "quotexmcandlereport")

# Candle Storage
hourly_candles = []

def send_telegram_msg(text):
    if not BOT_TOKEN or not CHAT_ID:
        print("Telegram Bot Token or Chat ID missing!")
        return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"}
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Telegram error: {e}")

def get_quotex_candles():
    """Quotex থেকে রিয়েলটাইম ক্যান্ডেল সংগ্রহের চেষ্টা করা"""
    try:
        from pyquotex import Client
        client = Client(email=EMAIL, password=PASSWORD)
        check, reason = client.connect()
        if check:
            # USDBRL_otc এর শেষ ৬০টি ১ মিনিটের ক্যান্ডেল নিয়ে আসা
            candles = client.get_candles("USDBRL_otc", 60)
            client.close()
            return candles
    except Exception as e:
        print(f"Quotex Fetch Error: {e}")
    return []

def collect_minute_candle():
    """প্রতি মিনিটে ক্যান্ডেল ডাটা ট্র্যাক করা"""
    global hourly_candles
    candles = get_quotex_candles()
    if candles:
        last_candle = candles[-1]
        open_p = last_candle.get('open', 0)
        close_p = last_candle.get('close', 0)
        
        if close_p > open_p:
            candle_type = "🟢 Green"
        elif close_p < open_p:
            candle_type = "🔴 Red"
        else:
            candle_type = "⚪ Doji"
            
        now_bd = datetime.now(pytz.timezone('Asia/Dhaka'))
        time_str = now_bd.strftime("%I:%M %p")
        hourly_candles.append(f"{time_str} -> {candle_type}")
        print(f"Collected Candle: {time_str} -> {candle_type}")

def generate_hourly_report():
    """প্রতি ঘণ্টায় চূড়ান্ত রিপোর্ট তৈরি ও পাঠানো"""
    global hourly_candles
    tz_bd = pytz.timezone('Asia/Dhaka')
    now_bd = datetime.now(tz_bd)
    start_time = (now_bd - timedelta(hours=1)).strftime("%I:00 %p")
    end_time = now_bd.strftime("%I:00 %p")
    date_str = now_bd.strftime("%d-%m-%Y")

    # যদি লাইব কালেকশন খালি থাকে, ব্যাকআপ হিসেবে সরাসরি ৬০ ক্যান্ডেল আনা
    if not hourly_candles:
        raw_candles = get_quotex_candles()
        green_count = 0
        red_count = 0
        list_str = ""
        
        for idx, c in enumerate(raw_candles):
            o, cl = c.get('open', 0), c.get('close', 0)
            if cl > o:
                green_count += 1
                c_str = "🟢 Green"
            elif cl < o:
                red_count += 1
                c_str = "🔴 Red"
            else:
                c_str = "⚪ Doji"
            
            c_time = (now_bd - timedelta(minutes=60-idx)).strftime("%I:%M %p")
            list_str += f"{c_time} -> {c_str}\n"
    else:
        green_count = sum(1 for c in hourly_candles if "🟢" in c)
        red_count = sum(1 for c in hourly_candles if "🔴" in c)
        list_str = "\n".join(hourly_candles)

    report_msg = (
        f"<b>Quotex USD/BRL OTC 1m Report</b>\n"
        f"📊 <b>Asset:</b> USD/BRL (OTC)\n"
        f"📅 <b>তারিখ:</b> {date_str}\n"
        f"⏰ <b>সময় (BD):</b> {start_time} - {end_time}\n"
        f"⏱ <b>টাইমফ্রেম:</b> 1 min\n\n"
        f"📋 <b>প্রতি মিনিটের ক্যান্ডেল লিস্ট:</b>\n"
        f"{list_str if list_str else 'ডাটা উপলব্ধ নয়'}\n\n"
        f"📊 <b>মোট হিসাব:</b>\n"
        f"🟢 Green: {green_count} | 🔴 Red: {red_count}"
    )

    send_telegram_msg(report_msg)
    hourly_candles = []  # রিসেট করা

# শিডিউল তৈরি
schedule.every(1).minutes.do(collect_minute_candle)
schedule.every().hour.at(":00").do(generate_hourly_report)

def run_scheduler():
    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    print("Bot is starting...")
    run_scheduler()
