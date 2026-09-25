import datetime
import os
import threading
import time
from flask import Flask
import requests
import schedule
from pyquotex import Quotex

# ================= Flask Web Server (Render Port Fix) =================
app = Flask(__name__)


@app.route("/")
def home():
    return "Quotex Candle Counter Bot is Running Live!"


def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)


# ================= কনফিগারেশন =================
BOT_TOKEN = "8518587756:AAGMOv5UTuCekmx5asuQr7vmVh_KKxFT534"
CHANNEL_ID = "@quotex_1m_candle_report"

QUOTEX_EMAIL = "quotexmcandlereport@gmail.com"
QUOTEX_PASSWORD = "quotexmcandlereport"

ASSET = "USDBRL_otc"
# ===============================================


def send_telegram_msg(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHANNEL_ID, "text": text, "parse_mode": "Markdown"}
    try:
        response = requests.post(url, data=payload)
        if response.status_code == 200:
            print("Telegram message sent successfully.")
        else:
            print(f"Failed to send message: {response.text}")
    except Exception as e:
        print(f"Error sending message: {e}")


def fetch_and_send_hourly_report():
    print(f"[{datetime.datetime.now()}] Fetching candle data for {ASSET}...")

    client = Quotex(email=QUOTEX_EMAIL, password=QUOTEX_PASSWORD)
    check_connect, reason = client.connect()

    if not check_connect:
        print(f"Quotex Connection failed: {reason}")
        return

    candles = client.get_candles(ASSET, 60, 3600, time.time())

    green_count = 0
    red_count = 0

    for candle in candles:
        if candle["close"] > candle["open"]:
            green_count += 1
        elif candle["close"] < candle["open"]:
            red_count += 1

    client.close()

    now = datetime.datetime.now()
    current_date = now.strftime("%d-%m-%Y")
    previous_hour = (now - datetime.timedelta(hours=1)).strftime("%I:00 %p")
    current_hour = now.strftime("%I:00 %p")
    time_range = f"{previous_hour} - {current_hour}"

    caption = (
        f"📊 **Asset:** USD/BRL (OTC)\n"
        f"📅 **তারিখ:** {current_date}\n"
        f"⏰ **সময়:** {time_range}\n"
        f"⏱️ **টাইমফ্রেম:** 1 min\n\n"
        f"🟢 **Green Candle:** {green_count}\n"
        f"🔴 **Red Candle:** {red_count}"
    )

    send_telegram_msg(caption)


def run_scheduler():
    schedule.every().hour.at(":00").do(fetch_and_send_hourly_report)
    print("Quotex Hourly Candle Counter Bot Started...")
    while True:
        schedule.run_pending()
        time.sleep(1)


if __name__ == "__main__":
    # ব্যাকগ্রাউন্ডে শেডিউলার চালু রাখা
    t = threading.Thread(target=run_scheduler)
    t.daemon = True
    t.start()

    # ওয়েব সার্ভার চালু করা (যা রেন্ডারের পোর্ট ওপেন করবে)
    run_web_server()
