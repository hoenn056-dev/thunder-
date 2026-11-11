import streamlit as st
import pandas as pd
import yfinance as yf
import time
import google.generativeai as genai
import requests
import pandas_ta_classic as ta
import numpy as np
from streamlit_lightweight_charts import renderLightweightCharts

st.set_page_config(layout="wide", page_title="Thunder Pro", initial_sidebar_state="expanded")
st.markdown("""<style>#MainMenu {visibility: hidden;} footer {visibility: hidden;} .block-container {padding-top: 1rem;}</style>""", unsafe_allow_html=True)

st.title("⚡ Thunder - Institutional Analyst")

# ================= 1. الإعدادات الجانبية =================
with st.sidebar:
    st.header("إعدادات السوق")
    symbol = st.selectbox("اختر الزوج", ["USD/JPY", "EUR/USD", "GBP/USD", "AUD/USD", "USD/CAD"])
    timeframe = st.selectbox("الإطار الزمني", ["1h", "4h", "1d", "15m"], index=0)
    
    # تحويل اسم الزوج ليتوافق مع ياهو فاينانس
    yf_symbol = symbol.replace("/", "") + "=X"
    
    st.divider()
    st.write("💡 **ملاحظة:** البيانات مجانية وقد تتأخر دقيقة.")

# ================= 2. إعداد الذكاء الاصطناعي =================
try:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    model = genai.GenerativeModel('gemini-flash-latest')
except Exception as e:
    st.error(f"خطأ في مفتاح Gemini: {e}")

def send_telegram_message(message):
    try:
        token = st.secrets["TELEGRAM_TOKEN"]
        chat_id = st.secrets["TELEGRAM_CHAT_ID"]
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {"chat_id": chat_id, "text": message}
        response = requests.post(url, json=payload)
        return response.status_code == 200
    except:
        return False

# ================= 3. جلب البيانات والتحليل =================
@st.cache_data(ttl=300)
def get_analysis(sym, tf):
    # جلب البيانات
    df = yf.download(sym, period="3mo", interval=tf, auto_adjust=True)
    if df.empty: return None
    
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df.reset_index(inplace=True)
    
    time_col = 'Datetime' if 'Datetime' in df.columns else 'Date'
    df['time'] = pd.to_datetime(df[time_col]).apply(lambda x: int(time.mktime(x.timetuple())))
    df.columns = [c.lower() for c in df.columns]
    
    # حساب المؤشرات
    df['rsi'] = ta.rsi(df['close'], length=14)
    macd = ta.macd(df['close'])
    df['macd'] = macd['MACD_12_26_9']
    df['macd_signal'] = macd['MACDs_12_26_9']
    df['atr'] = ta.atr(df['high'], df['low'], df['close'], length=14)
    
    # حساب المتوسطات
    df['ema50'] = ta.ema(df['close'], length=50)
    
    # حساب البيفوت (الدعم والمقاومة)
    last = df.iloc[-1]
    pivot = (last['high'] + last['low'] + last['close']) / 3
    r1 = (2 * pivot) - last['low']
    s1 = (2 * pivot) - last['high']
    
    # خطة الصفقة
    current_price = last['close']
    atr = last['atr']
    if current_price > pivot: # اتجاه صاعد
        entry = current_price
        tp = entry + (atr * 2)
        sl = entry - (atr * 1.5)
        direction = "شراء (Long)"
    else:
        entry = current_price
        tp = entry - (atr * 2)
        sl = entry + (atr * 1.5)
        direction = "بيع (Short)"
        
    return df, current_price, last['rsi'], last['macd'], pivot, r1, s1, direction, entry, tp, sl

try:
    df, price, rsi, macd, pivot, r1, s1, direction, entry, tp, sl = get_analysis(yf_symbol, timeframe)
except:
    st.error("تعذر جلب البيانات. قد يكون الزوج مغلقاً.")
    st.stop()

# ================= 4. واجهة المستخدم =================
# عرض البطاقات العلوية
col1, col2, col3, col4 = st.columns(4)
col1.metric("السعر الحالي", f"{price:.3f}")
col2.metric("RSI (14)", f"{rsi:.1f}", delta="تشبع شراء" if rsi > 70 else "تشبع بيع" if rsi < 30 else "محايد")
col3.metric("المقاومة (R1)", f"{r1:.3f}")
col4.metric("الدعم (S1)", f"{s1:.3f}")

st.divider()

# التبويبات
tab_chart, tab_trade, tab_chat = st.tabs(["📈 الرسم البياني", "🎯 خطة الصفقة", "🤖 المحلل الذكي"])

with tab_chart:
    chartOptions = {"height": 450, "layout": {"textColor": '#d1d4dc', "background": {"type": 'solid', "color": '#0a0a0f'}}, "grid": {"vertLines": {"color": '#1e1e2d'}, "horzLines": {"color": '#1e1e2d'}}, "timeScale": {"timeVisible": True}}
    candles = [{"type": 'Candlestick', "data": df[['time', 'open', 'high', 'low', 'close']].to_dict('records'), "options": {"upColor": '#26a69a', "downColor": '#ef5350'}}]
    ema = [{"type": 'Line', "data": df[['time', 'ema50']].rename(columns={'ema50': 'value'}).to_dict('records'), "options": {"color": '#f59e0b', "lineWidth": 2}}]
    renderLightweightCharts([{"chart": chartOptions, "series": candles + ema}], 'chart1')

with tab_trade:
    st.subheader(f"الخطة المقترحة: {direction}")
    c1, c2, c3 = st.columns(3)
    c1.info(f"**نقطة الدخول**\n\n{entry:.3f}")
    c2.success(f"**هدف الربح (TP)**\n\n{tp:.3f}")
    c3.error(f"**وقف الخسارة (SL)**\n\n{sl:.3f}")
    
    st.write(f"**نسبة المخاطرة للربح (R/R):** 1 : 1.33")
    st.write(f"**المؤشرات:** MACD = {macd:.3f} | EMA 50 = {df['ema50'].iloc[-1]:.3f}")

with tab_chat:
    st.markdown(f"**السياق الحالي:** {symbol} على إطار {timeframe}. السعر {price:.3f}. اتجاه {direction}.")
    
    if "messages" not in st.session_state:
        st.session_state.messages = []

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if prompt := st.chat_input("اسأل Thunder (مثلاً: هل أدخل الآن؟)"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("جاري تحليل السوق..."):
                try:
                    # إعطاء الذكاء الاصطناعي كل الأرقام
                    context = f"""
                    Symbol: {symbol} ({timeframe})
                    Current Price: {price:.3f}
                    Trend: {direction}
                    Entry: {entry:.3f}, TP: {tp:.3f}, SL: {sl:.3f}
                    RSI: {rsi:.1f}, MACD: {macd:.3f}
                    Pivot: {pivot:.3f}, R1: {r1:.3f}, S1: {s1:.3f}
                    """
                    response = model.generate_content(f"You are a pro trader. Based on this data:\n{context}\nAnswer the user in Arabic precisely: {prompt}")
                    st.markdown(response.text)
                    st.session_state.messages.append({"role": "assistant", "content": response.text})
                except Exception as e:
                    st.error(f"خطأ: {e}")

    st.divider()
    if st.button("📤 إرسال الخطة إلى تليجرام"):
        alert_msg = f"⚡ *Thunder Alert* ⚡\nالزوج: {symbol}\nالاتجاه: {direction}\nالدخول: {entry:.3f}\nالهدف: {tp:.3f}\nوقف الخسارة: {sl:.3f}"
        if send_telegram_message(alert_msg):
            st.success("تم الإرسال بنجاح!")
        else:
            st.error("فشل الإرسال. تأكد من إعدادات Chat ID.")
