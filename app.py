import streamlit as st
import pandas as pd
import yfinance as yf
import time
import requests
import pandas_ta_classic as ta
import google.generativeai as genai
from streamlit_lightweight_charts import renderLightweightCharts

st.set_page_config(layout="wide", page_title="Thunder Pro", initial_sidebar_state="expanded")
st.markdown("""<style>#MainMenu {visibility: hidden;} footer {visibility: hidden;} .block-container {padding-top: 1rem;}</style>""", unsafe_allow_html=True)
st.title("⚡ Thunder - Institutional Trading Dashboard")

# ================= 1. الإعدادات الجانبية =================
with st.sidebar:
    st.header("إعدادات السوق")
    symbol = st.selectbox("اختر الزوج", ["USD/JPY", "EUR/USD", "GBP/USD", "AUD/USD", "USD/CAD"])
    timeframe = st.selectbox("الإطار الزمني", ["15m", "1h", "4h", "1d"], index=1)
    yf_symbol = symbol.replace("/", "") + "=X"

# ================= 2. إعداد الذكاء الاصطناعي وتليجرام =================
try:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    model = genai.GenerativeModel('gemini-flash-latest')
except Exception as e:
    pass # سيتم التعامل معها عند الحاجة

def send_telegram_alert(text):
    try:
        token = st.secrets["TELEGRAM_TOKEN"]
        chat_id = st.secrets["TELEGRAM_CHAT_ID"]
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {"chat_id": chat_id, "text": text}
        res = requests.post(url, json=payload)
        
        if res.status_code == 200:
            return True, "تم الإرسال بنجاح!"
        else:
            # استخراج سبب الخطأ من تليجرام (مثلاً chat not found)
            error_desc = res.json().get("description", "خطأ غير معروف")
            return False, f"رفض تليجرام الطلب: {error_desc}"
    except Exception as e:
        return False, f"خطأ في الكود أو الإعدادات: {e}"

# ================= 3. دوال التحليل والبيانات =================
@st.cache_data(ttl=300)
def get_market_data(sym, tf):
    if tf == "15m": period = "5d"
    elif tf == "1h": period = "1mo"
    else: period = "3mo"

    df = yf.download(sym, period=period, interval=tf, auto_adjust=True)
    if df.empty: return None
        
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    
    df.columns = [c.lower() for c in df.columns]
    df['rsi'] = ta.rsi(df['close'], length=14)
    df['ema50'] = ta.ema(df['close'], length=50)
    df['atr'] = ta.atr(df['high'], df['low'], df['close'], length=14)
    return df

# جلب البيانات
df = get_market_data(yf_symbol, timeframe)

if df is None or len(df) < 50:
    st.error("تعذر جلب البيانات الكافية. جرّب إطاراً زمنياً آخر.")
    st.stop()

last_candle = df.iloc[-1]
current_price = float(last_candle['close'])
rsi_value = float(last_candle['rsi']) if not pd.isna(last_candle['rsi']) else 50.0
atr_value = float(last_candle['atr']) if not pd.isna(last_candle['atr']) else 0.1

# ================= 4. المقاييس العلوية =================
col1, col2, col3, col4 = st.columns(4)
col1.metric("السعر الحالي", f"{current_price:.3f}")
col2.metric("مؤشر RSI (14)", f"{rsi_value:.1f}", delta="تشبع شراء" if rsi_value > 70 else "تشبع بيع" if rsi_value < 30 else "محايد")
col3.metric("تقلب ATR", f"{atr_value:.3f}")
col4.metric("الإطار الزمني", timeframe.upper())

st.divider()

# ================= 5. التبويبات =================
tab_chart, tab_trade, tab_chat = st.tabs(["📈 شارت TradingView", "🎯 خطة التداول", "🤖 المحلل الذكي"])

with tab_chart:
    chart_df = df.reset_index()
    time_col = 'Datetime' if 'Datetime' in chart_df.columns else 'Date'
    chart_df['time'] = pd.to_datetime(chart_df[time_col]).apply(lambda x: int(time.mktime(x.timetuple())))
    
    candles = [{"type": 'Candlestick', "data": chart_df[['time', 'open', 'high', 'low', 'close']].to_dict('records'), "options": {"upColor": '#26a69a', "downColor": '#ef5350', "borderVisible": False}}]
    ema_data = chart_df[['time', 'ema50']].dropna().rename(columns={'ema50': 'value'})
    ema = [{"type": 'Line', "data": ema_data.to_dict('records'), "options": {"color": '#f59e0b', "lineWidth": 2}}]

    chartOptions = {"height": 520, "layout": {"textColor": '#d1d4dc', "background": {"type": 'solid', "color": '#0a0a0f'}}, "grid": {"vertLines": {"color": '#1e1e2d'}, "horzLines": {"color": '#1e1e2d'}}, "timeScale": {"timeVisible": True}, "handleScroll": True, "handleScale": True}
    renderLightweightCharts([{"chart": chartOptions, "series": candles + ema}], 'chart1')

with tab_trade:
    st.subheader("إدارة المخاطر والصفقة المقترحة")
    if current_price > df['ema50'].iloc[-1]:
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
        success, response_msg = send_telegram_alert(msg)
        if success:
            st.success(response_msg)
        else:
            st.error(response_msg) # سيعرض لك سبب الرفض بالضبط

with tab_chat:
    st.subheader("المحلل الذكي (Thunder AI)")
    
    if "messages" not in st.session_state:
        st.session_state.messages = []

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if prompt := st.chat_input("اسأل Thunder عن السوق..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("جاري التحليل..."):
                try:
                    context = f"Symbol: {symbol} ({timeframe})\nCurrent Price: {current_price:.3f}\nTrend: {direction}\nRSI: {rsi_value:.1f}\nATR: {atr_value:.3f}"
                    response = model.generate_content(f"You are a pro trader. Data:\n{context}\nAnswer in Arabic: {prompt}")
                    st.markdown(response.text)
                    st.session_state.messages.append({"role": "assistant", "content": response.text})
                except Exception as e:
                    st.error(f"خطأ في الذكاء الاصطناعي: {e}")
