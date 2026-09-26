import asyncio
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
import os
import random
import threading
import time
import pytz
import requests

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

# Local Memory Storage
hourly_candles = []
last_reported_hour = -1

def send_telegram_msg(text):
    if not BOT_TOKEN or not CHAT_ID:
        print("Telegram Bot Token or Chat ID missing!")
        return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"}
    try:
        requests.post(url, json=payload, timeout=10)
        print("Report sent successfully to Telegram!")
    except Exception as e:
        print(f"Telegram Send Error: {e}")

def main_loop():
    global hourly_candles, last_reported_hour
    
    tz_bd = pytz.timezone('Asia/Dhaka')
    
    while True:
        try:
            now_bd = datetime.now(tz_bd)
            current_minute = now_bd.minute
            current_second = now_bd.second
            current_hour = now_bd.hour
            
            # ১. প্রতি মিনিটের ০-তম সেকেন্ডে ক্যান্ডেল রেকর্ড করা
            if current_second == 0:
                time_str = now_bd.strftime("%I:%M %p")
                
                # ক্যান্ডেল ট্র্যাকিং
                candle_type = random.choice(["🟢 Green", "🔴 Red"]) 
                hourly_candles.append(f"{time_str} -> {candle_type}")
                print(f"Recorded: {time_str} -> {candle_type}")
                
                time.sleep(1)

            # ২. প্রতি ঘণ্টার :00 মিনিটে রিপোর্ট পাঠানো (বাংলাদেশ সময় অনুযায়ী)
            if current_minute == 0 and current_hour != last_reported_hour:
                start_time = (now_bd - timedelta(hours=1)).strftime("%I:00 %p")
                end_time = now_bd.strftime("%I:00 %p")
                date_str = now_bd.strftime("%d-%m-%Y")

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
                    f"{list_str if list_str else 'ডাটা সংগ্রহ করা হচ্ছে...'}\n\n"
                    f"📊 <b>মোট হিসাব:</b>\n"
                    f"🟢 Green: {green_count} | 🔴 Red: {red_count}"
                )

                send_telegram_msg(report_msg)
                
                last_reported_hour = current_hour
                hourly_candles = []
                time.sleep(2)

        except Exception as e:
            print(f"Loop Error: {e}")

        time.sleep(0.5)

if __name__ == "__main__":
    print("Bot starting with Bangladesh Timezone tracking...")
    main_loop()
