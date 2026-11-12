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
    status_report = f"🕒 *تحديث السوق* ({datetime.now().strftime('%H:%M')} UTC)\n\n"

    for sym in pairs:
        try:
            df = yf.download(sym, period="1d", interval="5m", progress=False)
            if df.empty: continue
            if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
            df.columns = [c.lower() for c in df.columns]
            
            df['rsi'] = ta.rsi(df['close'], length=14)
            last = df.iloc[-1]
            
            symbol_name = sym.replace("=X", "")
            rsi_val = float(last['rsi'])
            price_val = float(last['close'])
            
            # إضافة حالة الزوج إلى التقرير
            status_report += f"• {symbol_name}: السعر {price_val:.3f} | RSI: {rsi_val:.1f}\n"
            
            if rsi_val < 30:
                key = f"{sym}_BUY"
                if key not in state:
                    alerts.append(f"🟢 *فرصة شراء* | {symbol_name}\nالسعر: {price_val:.3f}\nRSI: {rsi_val:.1f}")
                    state[key] = "active"
            elif rsi_val > 70:
                key = f"{sym}_SELL"
                if key not in state:
                    alerts.append(f"🔴 *فرصة بيع* | {symbol_name}\nالسعر: {price_val:.3f}\nRSI: {rsi_val:.1f}")
                    state[key] = "active"
            else:
                # إزالة التنبيهات القديمة عند خروج السعر من المنطقة
                state.pop(f"{sym}_BUY", None)
                state.pop(f"{sym}_SELL", None)
                
        except Exception:
            pass

    if alerts:
        send_alert("⚡ *تنبيه فرص تداول* ⚡\n\n" + "\n\n".join(alerts))
    
    # إرسال تقرير الحالة مع كل فحص (كل 5 دقائق)
    send_alert(status_report)
    save_state(state)

if __name__ == "__main__":
    scan_market()
