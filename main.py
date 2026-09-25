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

    # গত ১ ঘণ্টার (৩৬০০ সেকেন্ড) ১ মিনিটের ক্যান্ডেল ডাটা
    candles = client.get_candles(ASSET, 60, 3600, time.time())
    client.close()

    # বাংলাদেশ সময় (UTC+6) অ্যাডজাস্টমেন্ট
    bd_now = datetime.datetime.utcnow() + datetime.timedelta(hours=6)
    current_date = bd_now.strftime("%d-%m-%Y")
    previous_hour = (bd_now - datetime.timedelta(hours=1)).strftime("%I:00 %p")
    current_hour = bd_now.strftime("%I:00 %p")
    time_range = f"{previous_hour} - {current_hour}"

    report_lines = []
    green_count = 0
    red_count = 0

    for candle in candles:
        # ক্যান্ডেলের সময়কে বাংলাদেশ সময়ের ফরম্যাটে নেওয়া
        c_time = datetime.datetime.utcfromtimestamp(
            candle["time"]
        ) + datetime.timedelta(hours=6)
        time_str = c_time.strftime("%I:%M %p")

        if candle["close"] > candle["open"]:
            report_lines.append(f"`{time_str}` 🟢 Green")
            green_count += 1
        elif candle["close"] < candle["open"]:
            report_lines.append(f"`{time_str}` 🔴 Red")
            red_count += 1
        else:
            report_lines.append(f"`{time_str}` ⚪ Doji")

    candle_details = "\n".join(report_lines)

    caption = (
        f"📊 **Asset:** USD/BRL (OTC)\n"
        f"📅 **তারিখ:** {current_date}\n"
        f"⏰ **সময় (BD):** {time_range}\n"
        f"⏱️ **টাইমফ্রেম:** 1 min\n\n"
        f"📋 **প্রতি মিনিটের ক্যান্ডেল লিস্ট:**\n"
        f"{candle_details}\n\n"
        f"📊 **মোট হিসাব:**\n"
        f"🟢 Green: {green_count} | 🔴 Red: {red_count}"
    )

    send_telegram_msg(caption)


def run_scheduler():
    # বাংলাদেশ সময় অনুযায়ী প্রতি ঘণ্টার ০০ মিনিটে রান করবে
    schedule.every().hour.at(":00").do(fetch_and_send_hourly_report)
    print("Quotex Hourly Candle Counter Bot Started...")
    while True:
        schedule.run_pending()
        time.sleep(1)


if __name__ == "__main__":
    t = threading.Thread(target=run_scheduler)
    t.daemon = True
    t.start()

    run_web_server()
