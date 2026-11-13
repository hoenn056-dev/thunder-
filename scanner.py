import os, requests, yfinance as yf, pandas as pd
import pandas_ta_classic as ta
from datetime import datetime, timezone
from curl_cffi import requests as curl_requests

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

def send_alert(msg):
    requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", 
                  json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"})

# إنشاء جلسة تحاكي متصفح كروم لتجنب حظر ياهو
def get_yf_session():
    try:
        session = curl_requests.Session(impersonate="chrome120")
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
        return session
    except Exception:
        return None

def check_market_time():
    now_utc = datetime.now(timezone.utc)
    current_hour = now_utc.hour
    day_of_week = now_utc.weekday()

    if day_of_week >= 5:
        return "🛑 *السوق مغلق:* اليوم هو عطلة نهاية الأسبوع. لا تتداول."

    if current_hour == 7:
        return "🔔 *استعد:* جلسة لندن تفتح بعد ساعة!\nالسيولة بدأت تتحرك. راقب: GBP/USD, EUR/USD."

    if current_hour == 12:
        return "🔔 *استعد:* جلسة نيويورك تفتح بعد ساعة!\nهذا هو وقت تداخل لندن ونيويورك (أقوى سيولة). راقب: USD/JPY."

    if current_hour in [21, 22, 23, 0, 1, 2, 3]:
        return "💤 *السوق هادئ جداً الآن:* السيولة منخفضة جداً. حركة السعر قد تكون عشوائية."

    if current_hour in [13, 14, 15, 16]:
        return "🔥 *ذروة السوق:* أفضل وقت للدخول في صفقات سريعة."

    return None

def scan_pairs():
    pairs = ["USDJPY=X", "EURUSD=X", "GBPUSD=X", "AUDUSD=X"]
    session = get_yf_session()
    alerts = []
    
    for sym in pairs:
        try:
            df = yf.download(sym, period="1d", interval="15m", progress=False, session=session)
            if df.empty: continue
            
            if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
            df.columns = [c.lower() for c in df.columns]
            
            df['rsi'] = ta.rsi(df['close'], length=14)
            last = df.iloc[-1]
            
            if last['rsi'] < 30:
                alerts.append(f"🟢 *فرصة شراء* | {sym.replace('=X','')}\nالسعر: {last['close']:.3f}\nRSI: {last['rsi']:.1f}")
            elif last['rsi'] > 70:
                alerts.append(f"🔴 *فرصة بيع* | {sym.replace('=X','')}\nالسعر: {last['close']:.3f}\nRSI: {last['rsi']:.1f}")
        except Exception as e:
            print(f"Error scanning {sym}: {e}")
            
    if alerts:
        send_alert("⚡ *تنبيه فرص تداول* ⚡\n\n" + "\n\n".join(alerts))

if __name__ == "__main__":
    time_alert = check_market_time()
    if time_alert:
        send_alert(time_alert)
        
    scan_pairs()
