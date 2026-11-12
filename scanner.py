import os, requests, yfinance as yf, pandas as pd
import pandas_ta_classic as ta
from datetime import datetime, timezone

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

def send_alert(msg):
    requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", 
                  json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"})

def check_market_time():
    # توقيت UTC هو المعيار العالمي للفوركس
    now_utc = datetime.now(timezone.utc)
    current_hour = now_utc.hour
    day_of_week = now_utc.weekday() # 0 هو الاثنين، 4 هو الجمعة، 5 و 6 هي عطلة

    # 1. إغلاق السوق في عطلة نهاية الأسبوع
    if day_of_week >= 5:
        return "🛑 *السوق مغلق:* اليوم هو عطلة نهاية الأسبوع. لا تتداول."

    # 2. قبل افتتاح لندن بساعة (الساعة 7 صباحاً بتوقيت UTC)
    if current_hour == 7:
        return "🔔 *استعد:* جلسة لندن تفتح بعد ساعة!\nالسيولة بدأت تتحرك. راقب: GBP/USD, EUR/USD.\nننصح بعدم الدخول حتى تظهر إشارة قوية."

    # 3. قبل افتتاح نيويورك بساعة (الساعة 12 ظهراً بتوقيت UTC)
    if current_hour == 12:
        return "🔔 *استعد:* جلسة نيويورك تفتح بعد ساعة!\nهذا هو وقت تداخل لندن ونيويورك (أقوى سيولة).\nراقب: USD/JPY, XAU/USD (الذهب)."

    # 4. أوقات هدوء السوق (الجلسة الآسيوية المتأخرة وبعد إغلاق نيويورك)
    if current_hour in [21, 22, 23, 0, 1, 2, 3]:
        return "💤 *السوق هادئ جداً الآن:* السيولة منخفضة جداً. حركة السعر قد تكون عشوائية (Fakeouts).\nننصح بالابتعاد وعدم المخاطرة."

    # 5. ذروة النشاط (تداخل لندن ونيويورك)
    if current_hour in [13, 14, 15, 16]:
        return "🔥 *ذروة السوق (Prime Time):* أفضل وقت للدخول في صفقات سريعة. السيولة عالية جداً."

    return None # لا ترسل رسالة في الأوقات العادية

if __name__ == "__main__":
    alert_msg = check_market_time()
    if alert_msg:
        send_alert(alert_msg)
