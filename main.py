import asyncio
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
import os
import threading
import time
import pytz
import requests

# Quotex ইমপোর্ট
from quotexpy import Quotex

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
BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
CHAT_ID = os.environ.get("CHAT_ID", "").strip()
QX_EMAIL = os.environ.get("QUOTEX_EMAIL", "").strip()
QX_PASSWORD = os.environ.get("QUOTEX_PASSWORD", "").strip()

hourly_candles = []
last_reported_hour = -1

def send_telegram_msg(text):
    if not BOT_TOKEN or not CHAT_ID:
        print("Error: BOT_TOKEN or CHAT_ID missing!")
        return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"}
    try:
        res = requests.post(url, json=payload, timeout=10)
        print(f"Telegram API Status: {res.status_code}")
    except Exception as e:
        print(f"Telegram Exception: {e}")

async def main_loop():
    global hourly_candles, last_reported_hour
    tz_bd = pytz.timezone('Asia/Dhaka')

    # Quotex API কানেকশন (headless=True দেওয়া হয়েছে যেন ব্রাউজার ব্যাকগ্রাউন্ডে চলে)
    client = Quotex(email=QX_EMAIL, password=QX_PASSWORD, headless=True)
    
    try:
        check_connect, reason = await client.connect()
    except Exception as e:
        check_connect = False
        reason = str(e)

    if check_connect:
        print("✅ Quotex Live Market Data Connected!")
        send_telegram_msg("✅ <b>Quotex Live Market Data Connected!</b>\nলাইভ ক্যান্ডেল গণনা শুরু হয়েছে।")
    else:
        print(f"❌ Quotex Connection Failed: {reason}")
        send_telegram_msg(f"❌ Quotex কানেকশন ব্যর্থ হয়েছে: {reason}")
        return

    asset = "USD/BRL_otc"

    while True:
        try:
            now_bd = datetime.now(tz_bd)
            current_minute = now_bd.minute
            current_second = now_bd.second
            current_hour = now_bd.hour

            # প্রতি মিনিটের ০০ সেকেন্ডে Quotex থেকে আসল ক্যান্ডেল ডাটা ফেচ
            if current_second == 0:
                time_str = now_bd.strftime("%I:%M %p")
                
                # Quotex থেকে ১ মিনিটের ক্যান্ডেল নেওয়া
                candles = await client.get_candles(asset, 60)
                if candles:
                    last_candle = candles[-1]
                    open_price = last_candle['open']
                    close_price = last_candle['close']

                    if close_price > open_price:
                        candle_type = "🟢 Green"
                    elif close_price < open_price:
                        candle_type = "🔴 Red"
                    else:
                        candle_type = "⚪ Doji"

                    hourly_candles.append(f"{time_str} -> {candle_type}")
                    print(f"Real Candle [{time_str}]: {candle_type}")
                
                await asyncio.sleep(1)

            # প্রতি ঘণ্টার :০০ মিনিটে টেলিগ্রামে ঘণ্টা রিপোর্ট পোস্ট
            if current_minute == 0 and current_hour != last_reported_hour:
                start_time = (now_bd - timedelta(hours=1)).strftime("%I:00 %p")
                end_time = now_bd.strftime("%I:00 %p")
                date_str = now_bd.strftime("%d-%m-%Y")

                green_count = sum(1 for c in hourly_candles if "🟢" in c)
                red_count = sum(1 for c in hourly_candles if "🔴" in c)
                doji_count = sum(1 for c in hourly_candles if "⚪" in c)
                list_str = "\n".join(hourly_candles)

                report_msg = (
                    f"<b>Quotex USD/BRL OTC 1m Report</b>\n"
                    f"📊 <b>Asset:</b> USD/BRL (OTC)\n"
                    f"📅 <b>তারিখ:</b> {date_str}\n"
                    f"⏰ <b>সময় (BD):</b> {start_time} - {end_time}\n"
                    f"⏱ <b>টাইমফ্রেম:</b> 1 min\n\n"
                    f"📋 <b>প্রতি মিনিটের ক্যান্ডেল লিস্ট:</b>\n"
                    f"{list_str if list_str else 'ডাটা পাওয়া যায়নি'}\n\n"
                    f"📊 <b>মোট হিসাব:</b>\n"
                    f"🟢 Green: {green_count} | 🔴 Red: {red_count} | ⚪ Doji: {doji_count}"
                )

                send_telegram_msg(report_msg)
                last_reported_hour = current_hour
                hourly_candles = []
                await asyncio.sleep(2)

        except Exception as e:
            print(f"Loop Error: {e}")

        await asyncio.sleep(0.5)

if __name__ == "__main__":
    print("Starting Quotex Live Bot...")
    asyncio.run(main_loop())
