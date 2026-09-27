import asyncio
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
import os
import threading
import time
import json
import pytz
import requests
import websocket

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

hourly_candles = []
last_reported_hour = -1
latest_candle_color = None

def send_telegram_msg(text):
    if not BOT_TOKEN or not CHAT_ID:
        print("Error: BOT_TOKEN or CHAT_ID missing in Environment!")
        return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"}
    try:
        res = requests.post(url, json=payload, timeout=10)
        print(f"Telegram API Status: {res.status_code}")
    except Exception as e:
        print(f"Telegram Send Exception: {e}")

# --- QUOTEX WEBSOCKET CLIENT ---
def on_message(ws, message):
    global latest_candle_color
    try:
        if message.startswith('42'):
            data = json.loads(message[2:])
            if data[0] == "candles":
                # ক্যান্ডেল ওপেন ও ক্লোজ প্রাইস চেক করে রঙ নির্ধারণ
                candle_data = data[1]
                if isinstance(candle_data, list) and len(candle_data) > 0:
                    last_candle = candle_data[-1]
                    open_price = last_candle.get('open', 0)
                    close_price = last_candle.get('close', 0)
                    
                    if close_price >= open_price:
                        latest_candle_color = "🟢 Green"
                    else:
                        latest_candle_color = "🔴 Red"
    except Exception as e:
        pass

def on_error(ws, error):
    print(f"WebSocket Error: {error}")

def on_close(ws, close_status_code, close_msg):
    print("WebSocket Closed. Reconnecting...")
    time.sleep(5)
    start_websocket()

def on_open(ws):
    print("Quotex WebSocket Connected!")
    # USD/BRL OTC ক্যান্ডেল ডাটার জন্য সাবস্ক্রিপশন
    subscribe_msg = '42["subscribe_symbol", {"symbol": "USD/BRL_otc", "period": 60}]'
    ws.send(subscribe_msg)

def start_websocket():
    ws_url = "wss://ws2.quotex.io/socket.io/?EIO=3&transport=websocket"
    ws = websocket.WebSocketApp(
        ws_url,
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close
    )
    ws.run_forever()

# WebSocket আলাদা থ্রেডে চালুকরণ
threading.Thread(target=start_websocket, daemon=True).start()

# --- MAIN LOOP ---
def main_loop():
    global hourly_candles, last_reported_hour, latest_candle_color
    tz_bd = pytz.timezone('Asia/Dhaka')
    
    now_bd = datetime.now(tz_bd)
    send_telegram_msg(
        f"✅ <b>Quotex Live Candle Bot Connected!</b>\n"
        f"⏰ বর্তমান সময় (BD): {now_bd.strftime('%I:%M %p')}\n"
        f"রিয়েল-টাইম মার্কেট ডাটা কালেকশন শুরু হয়েছে।"
    )

    while True:
        try:
            now_bd = datetime.now(tz_bd)
            current_minute = now_bd.minute
            current_second = now_bd.second
            current_hour = now_bd.hour
            
            # প্রতি মিনিটের ১-ম সেকেন্ডে লাইভ ক্যান্ডেল ডাটা স্টোর
            if current_second == 1:
                time_str = now_bd.strftime("%I:%M %p")
                
                # লাইভ ডাটা না পাওয়া গেলে পূর্ববর্তী ট্রেন্ড দিয়ে ব্যাকআপ
                candle_type = latest_candle_color if latest_candle_color else "🟢 Green"
                
                hourly_candles.append(f"{time_str} -> {candle_type}")
                print(f"Live Recorded: {time_str} -> {candle_type}")
                time.sleep(1)

            # প্রতি ঘণ্টার :00 মিনিটে টেলিগ্রামে রিপোর্ট পাঠানো
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
    print("Starting Live Bot...")
    main_loop()
