import streamlit as st
import pandas as pd
import yfinance as yf
import time
import requests
import pandas_ta_classic as ta
import google.generativeai as genai
from streamlit_lightweight_charts import renderLightweightCharts
from PIL import Image
import json

st.set_page_config(layout="wide", page_title="Thunder Pro", initial_sidebar_state="expanded")
st.markdown("""<style>#MainMenu {visibility: hidden;} footer {visibility: hidden;} .block-container {padding-top: 1rem;}</style>""", unsafe_allow_html=True)
st.title("⚡ Thunder - Multi-Agent Trading System")

# ================= 1. إعداد الذكاء الاصطناعي =================
try:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    # استخدام النموذج الأحدث لتجنب خطأ 404
    model = genai.GenerativeModel('gemini-1.5-flash-latest')
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

# ================= 2. الإعدادات الجانبية =================
with st.sidebar:
    st.header("إعدادات السوق")
    platform = st.radio("اختر المنصة:", ["تداول فوركس (Scalping)", "Pocket Option (Binary)"])
    symbol = st.selectbox("اختر الزوج", ["USD/JPY", "EUR/USD", "GBP/USD", "AUD/USD"])
    
    # تحديد الإطار الزمني بناءً على المنصة
    if platform == "Pocket Option (Binary)":
        timeframe = st.selectbox("الإطار الزمني (للبوت)", ["1m", "5m"], index=1)
    else:
        timeframe = st.selectbox("الإطار الزمني", ["15m", "1h", "4h"], index=0)
        
    yf_symbol = symbol.replace("/", "") + "=X"

# ================= 3. جلب البيانات =================
@st.cache_data(ttl=60) # تحديث أسرع للبيانات
def get_market_data(sym, tf):
    period = "1d" if tf in ["1m", "5m"] else "5d" if tf == "15m" else "1mo"
    df = yf.download(sym, period=period, interval=tf, auto_adjust=True)
    if df.empty: return None
    if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
    df.columns = [c.lower() for c in df.columns]
    
    df['rsi'] = ta.rsi(df['close'], length=14)
    df['ema50'] = ta.ema(df['close'], length=50)
    df['atr'] = ta.atr(df['high'], df['low'], df['close'], length=14)
    return df

df = get_market_data(yf_symbol, timeframe)

if df is None or len(df) < 20:
    st.error("تعذر جلب البيانات.")
    st.stop()

last_candle = df.iloc[-1]
current_price = float(last_candle['close'])

# ================= 4. التبويبات =================
tab_chart, tab_agents, tab_chat = st.tabs(["📈 الشارت", "🧠 المحللون المتعددون", "💬 الدردشة"])

with tab_chart:
    chart_df = df.reset_index()
    time_col = 'Datetime' if 'Datetime' in chart_df.columns else 'Date'
    chart_df['time'] = pd.to_datetime(chart_df[time_col]).apply(lambda x: int(time.mktime(x.timetuple())))
    
    candles = [{"type": 'Candlestick', "data": chart_df[['time', 'open', 'high', 'low', 'close']].dropna().to_dict('records'), "options": {"upColor": '#26a69a', "downColor": '#ef5350'}}]
    ema = [{"type": 'Line', "data": chart_df[['time', 'ema50']].dropna().rename(columns={'ema50': 'value'}).to_dict('records'), "options": {"color": '#f59e0b', "lineWidth": 2}}]
    
    chartOptions = {"height": 500, "layout": {"textColor": '#d1d4dc', "background": {"type": 'solid', "color": '#0a0a0f'}}, "grid": {"vertLines": {"color": '#1e1e2d'}, "horzLines": {"color": '#1e1e2d'}}, "timeScale": {"timeVisible": True}, "handleScroll": True, "handleScale": True}
    renderLightweightCharts([{"chart": chartOptions, "series": candles + ema}], 'chart1')

with tab_agents:
    st.subheader("🧠 غرفة التحليل (Multi-Agent)")
    st.write("ثلاثة محللين يقومون بتحليل السوق الآن...")
    
    if st.button("🚀 بدء التحليل الشامل", use_container_width=True):
        with st.spinner("جاري تشغيل المحللين..."):
            try:
                # تجهيز السياق
                recent_data = df.tail(5)[['open', 'high', 'low', 'close', 'rsi', 'ema50', 'atr']].to_string()
                
                prompt = f"""
                أنت فريق من 3 محللين ماليين محترفين. بيانات السوق الحالية لـ {symbol} على إطار {timeframe}:
                {recent_data}
                السعر الحالي: {current_price:.3f}
                
                المطلوب: قم بتحليل البيانات كفريق وتحديد خطة صفقة دقيقة.
                أريد الإجابة بتنسيق JSON فقط بهذا الشكل (بدون أي نصوص إضافية):
                {{
                    "technical_analysis": "رأي المحلل الفني في الاتجاه والمؤشرات",
                    "fundamental_analysis": "رأي محلل الأخبار والسياق العام",
                    "risk_manager_verdict": "رأي مدير المخاطر (نسبة الثقة من 0 إلى 100)",
                    "direction": "شراء" أو "بيع" أو "انتظار",
                    "entry_price": {current_price:.3f},
                    "trade_duration_minutes": "المدة المتوقعة للصفقة بالدقائق (مثال: 5 دقائق، 15 دقيقة)",
                    "tp": "هدف الربح",
                    "sl": "وقف الخسارة"
                }}
                """
                
                response = model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
                result = json.loads(response.text)
                
                # عرض النتائج
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.info("📊 المحلل الفني")
                    st.write(result.get('technical_analysis'))
                with col2:
                    st.warning("📰 محلل الأخبار")
                    st.write(result.get('fundamental_analysis'))
                with col3:
                    st.success(f"🛡️ مدير المخاطر (الثقة: {result.get('risk_manager_verdict')}%)")
                
                st.divider()
                st.subheader("📋 القرار النهائي")
                st.markdown(f"**الاتجاه:** {result.get('direction')}")
                st.markdown(f"**مدة الصفقة:** {result.get('trade_duration_minutes')}")
                st.markdown(f"**الدخول:** {result.get('entry_price')} | **الهدف:** {result.get('tp')} | **الوقف:** {result.get('sl')}")
                
                # إرسال لتليجرام
                msg = f"⚡ Thunder Multi-Agent ⚡\nالزوج: {symbol}\nالاتجاه: {result.get('direction')}\nالمدة: {result.get('trade_duration_minutes')}\nالدخول: {result.get('entry_price')}\nالهدف: {result.get('tp')}\nالوقف: {result.get('sl')}"
                if send_telegram_alert(msg):
                    st.success("تم إرسال التوصية إلى تليجرام!")
                    
            except Exception as e:
                st.error(f"خطأ في التحليل: {e}")

with tab_chat:
    st.subheader("المساعد الشخصي (مع دعم الصور)")
    
    if "messages" not in st.session_state:
        st.session_state.messages = []

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if "image" in message:
                st.image(message["image"])

    uploaded_file = st.file_uploader("ارفع صورة شارت (خاصة بـ Pocket Option) لتحليلها:", type=["png", "jpg", "jpeg"])

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
                    if uploaded_file:
                        img = Image.open(uploaded_file)
                        response = model.generate_content([f"أنت متداول محترف في Pocket Option. حلل هذه الصورة وحدد وقت الدخول والمدة المناسبة. سؤال: {prompt}", img])
                    else:
                        response = model.generate_content(f"أنت متداول محترف. السعر الحالي: {current_price}. أجب: {prompt}")
                    
                    st.markdown(response.text)
                    st.session_state.messages.append({"role": "assistant", "content": response.text})
                except Exception as e:
                    st.error(f"خطأ: {e}")
