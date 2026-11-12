import streamlit as st
import pandas as pd
import yfinance as yf
import time
import requests
import pandas_ta_classic as ta
import google.generativeai as genai
from streamlit_lightweight_charts import renderLightweightCharts
from PIL import Image
import threading

st.set_page_config(layout="wide", page_title="Thunder Pro", initial_sidebar_state="expanded")
st.markdown("""<style>#MainMenu {visibility: hidden;} footer {visibility: hidden;} .block-container {padding-top: 1rem;}</style>""", unsafe_allow_html=True)
st.title("⚡ Thunder - Institutional Trading Dashboard")

# ================= 1. إعداد الذكاء الاصطناعي =================
try:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    # استخدام نموذج مستقر ويدعم الصور
    model = genai.GenerativeModel('gemini-flash-latest')
except Exception as e:
    st.error(f"خطأ في مفتاح Gemini: {e}")

def send_telegram_alert(text):
    try:
        token = st.secrets["TELEGRAM_TOKEN"]
        chat_id = st.secrets["TELEGRAM_CHAT_ID"]
        res = requests.post(f"https://api.telegram.org/bot{token}/sendMessage", 
                            json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"})
        return res.status_code == 200
    except:
        return False

# ================= 2. دالة الخلفية لفحص السوق =================
def background_scanner():
    pairs = ["USD/JPY", "EUR/USD", "GBP/USD", "AUD/USD"]
    while True:
        found = False
        msg = "🔍 *تحديث السوق التلقائي*\n"
        for pair in pairs:
            try:
                df = yf.download(pair.replace("/", "") + "=X", period="5d", interval="1h", auto_adjust=True, progress=False)
                if not df.empty:
                    if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
                    df.columns = [c.lower() for c in df.columns]
                    df['rsi'] = ta.rsi(df['close'], length=14)
                    last = df.iloc[-1]
                    if last['rsi'] < 30:
                        msg += f"\n🟢 فرصة شراء {pair} (RSI: {last['rsi']:.1f})"
                        found = True
                    elif last['rsi'] > 70:
                        msg += f"\n🔴 فرصة بيع {pair} (RSI: {last['rsi']:.1f})"
                        found = True
            except:
                pass
        if found:
            send_telegram_alert(msg)
        time.sleep(3600) # يفحص كل ساعة

if "scanner_started" not in st.session_state:
    st.session_state.scanner_started = True
    threading.Thread(target=background_scanner, daemon=True).start()

# ================= 3. جلب البيانات =================
@st.cache_data(ttl=300)
def get_market_data(sym, tf):
    period = "5d" if tf == "15m" else "1mo" if tf == "1h" else "3mo"
    df = yf.download(sym, period=period, interval=tf, auto_adjust=True)
    if df.empty: return None
    if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
    df.columns = [c.lower() for c in df.columns]
    
    df['rsi'] = ta.rsi(df['close'], length=14)
    df['ema50'] = ta.ema(df['close'], length=50)
    df['atr'] = ta.atr(df['high'], df['low'], df['close'], length=14)
    bb = ta.bbands(df['close'], length=20)
    df['bb_upper'] = bb['BBU_20_2.0']
    df['bb_lower'] = bb['BBL_20_2.0']
    return df

# ================= 4. الإعدادات الجانبية =================
with st.sidebar:
    st.header("إعدادات السوق")
    symbol = st.selectbox("اختر الزوج", ["USD/JPY", "EUR/USD", "GBP/USD", "AUD/USD"])
    timeframe = st.selectbox("الإطار الزمني", ["15m", "1h", "4h"], index=1)
    yf_symbol = symbol.replace("/", "") + "=X"

df = get_market_data(yf_symbol, timeframe)

if df is None or len(df) < 50:
    st.error("تعذر جلب البيانات.")
    st.stop()

last_candle = df.iloc[-1]
current_price = float(last_candle['close'])
atr_value = float(last_candle['atr']) if not pd.isna(last_candle['atr']) else 0.1

# ================= 5. المقاييس العلوية =================
c1, c2, c3, c4 = st.columns(4)
c1.metric("السعر الحالي", f"{current_price:.3f}")
c2.metric("RSI", f"{last_candle['rsi']:.1f}")
c3.metric("ATR", f"{atr_value:.3f}")
c4.metric("الإطار", timeframe.upper())

st.divider()

# ================= 6. التبويبات (هذا هو السطر الذي كان ناقصاً) =================
tab_chart, tab_trade, tab_chat = st.tabs(["📈 شارت TradingView", "🎯 خطة التداول", "🤖 المحلل الذكي"])

with tab_chart:
    chart_df = df.reset_index()
    time_col = 'Datetime' if 'Datetime' in chart_df.columns else 'Date'
    chart_df['time'] = pd.to_datetime(chart_df[time_col]).apply(lambda x: int(time.mktime(x.timetuple())))
    
    candles = [{"type": 'Candlestick', "data": chart_df[['time', 'open', 'high', 'low', 'close']].dropna().to_dict('records'), "options": {"upColor": '#26a69a', "downColor": '#ef5350'}}]
    ema = [{"type": 'Line', "data": chart_df[['time', 'ema50']].dropna().rename(columns={'ema50': 'value'}).to_dict('records'), "options": {"color": '#f59e0b', "lineWidth": 2}}]
    
    chartOptions = {"height": 500, "layout": {"textColor": '#d1d4dc', "background": {"type": 'solid', "color": '#0a0a0f'}}, "grid": {"vertLines": {"color": '#1e1e2d'}, "horzLines": {"color": '#1e1e2d'}}, "timeScale": {"timeVisible": True}, "handleScroll": True, "handleScale": True}
    renderLightweightCharts([{"chart": chartOptions, "series": candles + ema}], 'chart1')

with tab_trade:
    st.subheader("إدارة المخاطر والصفقة المقترحة")
    if current_price > last_candle['ema50']:
        direction, color = "شراء (Long)", "green"
        tp, sl = current_price + (atr_value * 2), current_price - (atr_value * 1.5)
    else:
        direction, color = "بيع (Short)", "red"
        tp, sl = current_price - (atr_value * 2), current_price + (atr_value * 1.5)

    st.markdown(f"**الاتجاه العام:** :{color}[**{direction}**]")
    
    c1, c2, c3 = st.columns(3)
    c1.info(f"**نقطة الدخول**\n\n### {current_price:.3f}")
    c2.success(f"**هدف الربح (TP)**\n\n### {tp:.3f}")
    c3.error(f"**وقف الخسارة (SL)**\n\n### {sl:.3f}")
    
    if st.button("📤 إرسال خطة الصفقة إلى تليجرام", use_container_width=True):
        msg = f"⚡ Thunder Alert ⚡\nالزوج: {symbol} ({timeframe})\nالاتجاه: {direction}\nالدخول: {current_price:.3f}\nالهدف: {tp:.3f}\nوقف الخسارة: {sl:.3f}"
        if send_telegram_alert(msg):
            st.success("تم إرسال التنبيه إلى تليجرام بنجاح!")

with tab_chat:
    st.subheader("المحلل المؤسسي (مع دعم الصور)")
    
    if "messages" not in st.session_state:
        st.session_state.messages = []

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if "image" in message:
                st.image(message["image"])

    uploaded_file = st.file_uploader("ارفع صورة شارت لتحليلها:", type=["png", "jpg", "jpeg"])

    if prompt := st.chat_input("اسأل Thunder..."):
        user_msg = {"role": "user", "content": prompt}
        if uploaded_file:
            user_msg["image"] = uploaded_file
        st.session_state.messages.append(user_msg)
        
        with st.chat_message("user"):
            st.markdown(prompt)
            if uploaded_file:
                st.image(uploaded_file)

        with st.chat_message("assistant"):
            with st.spinner("جاري التحليل..."):
                try:
                    context = f"السعر: {current_price:.3f}, RSI: {last_candle['rsi']:.1f}"
                    if uploaded_file:
                        img = Image.open(uploaded_file)
                        response = model.generate_content([f"أنت متداول مؤسسي. حلل هذه الصورة. السياق: {context}. سؤال: {prompt}", img])
                    else:
                        response = model.generate_content(f"أنت متداول مؤسسي. السياق: {context}. أجب بالعربية: {prompt}")
                    
                    st.markdown(response.text)
                    st.session_state.messages.append({"role": "assistant", "content": response.text})
                except Exception as e:
                    st.error(f"خطأ: {e}")
