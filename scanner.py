import os, json, requests, yfinance as yf, pandas as pd
import pandas_ta_classic as ta
from datetime import datetime

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
STATE_FILE = "alert_state.json"

def send_alert(msg):
    requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", 
                  json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"})

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f: return json.load(f)
    return {}

def save_state(state):
    with open(STATE_FILE, "w") as f: json.dump(state, f)

def scan_market():
    pairs = ["USDJPY=X", "EURUSD=X", "GBPUSD=X", "AUDUSD=X"]
    state = load_state()
    alerts = []

    for sym in pairs:
        try:
            # جلب إطار 15 دقيقة و 1 ساعة
            for tf in ["15m", "1h"]:
                df = yf.download(sym, period="1d", interval=tf, progress=False)
                if df.empty: continue
                if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
                df.columns = [c.lower() for c in df.columns]
                
                df['rsi'] = ta.rsi(df['close'], length=14)
                df['ema50'] = ta.ema(df['close'], length=50)
                last = df.iloc[-1]
                
                # شرط الفرصة: RSI في منطقة التشبع + السعر يعبر EMA50
                if last['rsi'] < 30 and last['close'] > last['ema50']:
                    key = f"{sym}_{tf}_BUY"
                    if key not in state or state[key] != str(last['close'].round(3)):
                        alerts.append(f"🟢 *فرصة شراء* | {sym} ({tf})\nالسعر: {last['close']:.3f}\nRSI: {last['rsi']:.1f}")
                        state[key] = str(last['close'].round(3))
                
                elif last['rsi'] > 70 and last['close'] < last['ema50']:
                    key = f"{sym}_{tf}_SELL"
                    if key not in state or state[key] != str(last['close'].round(3)):
                        alerts.append(f"🔴 *فرصة بيع* | {sym} ({tf})\nالسعر: {last['close']:.3f}\nRSI: {last['rsi']:.1f}")
                        state[key] = str(last['close'].round(3))
        except Exception as e:
            pass

    if alerts:
        send_alert("⚡ *تحديث السوق التلقائي* ⚡\n\n" + "\n\n".join(alerts))
    
    save_state(state)

if __name__ == "__main__":
    scan_market()
