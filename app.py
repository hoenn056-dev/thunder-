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
import re

st.set_page_config(layout="wide", page_title="Thunder Pro", initial_sidebar_state="expanded")
st.markdown("""<style>#MainMenu {visibility: hidden;} footer {visibility: hidden;} .block-container {padding-top: 1rem;}</style>""", unsafe_allow_html=True)
st.title("⚡ Thunder - Smart Trading System")

# ================= 1. إعداد الذكاء الاصطناعي =================
try:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    # حل مشكلة 404 باستخدام النموذج الأحدث
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
    
    if platform == "Pocket Option (Binary)":
        timeframe = st.selectbox("الإطار الزمني", ["1m", "5m"], index=1)
    else:
        timeframe = st.selectbox("الإطار الزمني", ["15m", "1h", "4h"], index=0)
        
    yf_symbol = symbol.replace("/", "") + "=X"

# ================= 3. جلب البيانات =================
@st.cache_data(ttl=60)
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
    st.error("تعذر جلب البيانات. جرب إطاراً زمنياً آخر.")
    st.stop()

last_candle = df.iloc[-1]
current_price = float(last_candle['close'])
atr_value = float(last_candle['atr']) if not pd.isna(last_candle['atr']) else 0.1

# ================= 4. التبويبات =================
tab_chart, tab_trade, tab_agents, tab_chat = st.tabs([
    "📈 الشارت", 
    "🎯 خطة التداول الذكية", 
    "🧠 المحللون المتعددون", 
    "💬 الدردشة"
])

with tab_chart:
    chart_df = df.reset_index()
    time_col = 'Datetime' if 'Datetime' in chart_df.columns else 'Date'
    chart_df['time'] = pd.to_datetime(chart_df[time_col]).apply(lambda x: int(time.mktime(x.timetuple())))
    
    candles = [{"type": 'Candlestick', "data": chart_df[['time', 'open', 'high', 'low', 'close']].dropna().to_dict('records'), "options": {"upColor": '#26a69a', "downColor": '#ef5350'}}]
    ema = [{"type": 'Line', "data": chart_df[['time', 'ema50']].dropna().rename(columns={'ema50': 'value'}).to_dict('records'), "options": {"color": '#f59e0b', "lineWidth": 2}}]
    
    chartOptions = {"height": 500, "layout": {"textColor": '#d1d4dc', "background": {"type": 'solid', "color": '#0a0a0f'}}, "grid": {"vertLines": {"color": '#1e1e2d'}, "horzLines": {"color": '#1e1e2d'}}, "timeScale": {"timeVisible": True}, "handleScroll": True, "handleScale": True}
    renderLightweightCharts([{"chart": chartOptions, "series": candles + ema}], 'chart1')

with tab_trade:
    st.subheader("خطة التداول (توليد ذكي)")
    st.write("اضغط على الزر أدناه ليقوم الذكاء الاصطناعي بتحليل السوق وتحديد خطة كاملة تشمل **زمن الصفقة**.")
    
    if st.button("⚡ توليد خطة التداول الآن", use_container_width=True):
        with st.spinner("جاري تحليل السوق وتحديد زمن الصفقة..."):
            try:
                # إعطاء الذكاء الاصطناعي البيانات والمؤشرات
                recent_data = df.tail(3)[['open', 'high', 'low', 'close', 'rsi', 'ema50', 'atr']].to_string()
                
                prompt = f"""
                أنت متداول مؤسسي خبير. حلل البيانات التالية لزوج {symbol} على إطار {timeframe}.
                البيانات:
                {recent_data}
                السعر الحالي: {current_price:.3f}
                
                المنصة: {platform}.
                المطلوب: تحديد خطة صفقة دقيقة.
                أريد الإجابة بصيغة JSON فقط (بدون أي نصوص إضافية أو علامات Markdown):
                {{
                    "direction": "شراء" أو "بيع" أو "انتظار",
                    "entry_price": "سعر الدخول",
                    "tp": "هدف الربح",
                    "sl": "وقف الخسارة",
                    "trade_duration": "زمن الصفقة المتوقع بالدقائق (مثلاً: 3 دقائق، 15 دقيقة، أو ساعتين)",
                    "reasoning": "سبب مختصر جداً للقرار"
                }}
                """
                
                response = model.generate_content(prompt)
                
                # تنظيف الرد لضمان قراءة JSON بشكل صحيح
                clean_json = re.sub(r'```json\n|\n```', '', response.text).strip()
                plan = json.loads(clean_json)
                
                st.success(f"**القرار:** {plan['direction']} | **السبب:** {plan['reasoning']}")
                st.divider()
                
                # عرض الخطة في 4 أعمدة لتشمل زمن الصفقة
                c1, c2, c3, c4 = st.columns(4)
                c1.info(f"**نقطة الدخول**\n\n### {plan['entry_price']}")
                c2.success(f"**هدف الربح**\n\n### {plan['tp']}")
                c3.error(f"**وقف الخسارة**\n\n### {plan['sl']}")
                c4.warning(f"**زمن الصفقة**\n\n### {plan['trade_duration']}")
                
                # إرسال إلى تليجرام
                msg = f"⚡ *Thunder Trade Plan* ⚡\nالزوج: {symbol} ({timeframe})\nالقرار: {plan['direction']}\nالدخول: {plan['entry_price']}\nالهدف: {plan['tp']}\nالوقف: {plan['sl']}\n*زمن الصفقة:* {plan['trade_duration']}"
                if send_telegram_alert(msg):
                    st.toast("📤 تم إرسال الخطة إلى تليجرام!")
                    
            except Exception as e:
                st.error(f"حدث خطأ في التحليل: {e}")

with tab_agents:
    st.subheader("🧠 غرفة التحليل (Multi-Agent)")
    st.write("ثلاثة محللين يحللون السوق بالتوازي.")
    
    if st.button("🚀 بدء التحليل الشامل", use_container_width=True):
        with st.spinner("جاري تشغيل المحللين..."):
            try:
                recent_data = df.tail(5)[['open', 'high', 'low', 'close', 'rsi', 'ema50', 'atr']].to_string()
                prompt = f"""
                أنت فريق من 3 محللين. بيانات {symbol} ({timeframe}):
                {recent_data}
                السعر: {current_price:.3f}
                أريد JSON فقط:
                {{
                    "technical": "رأي المحلل الفني",
                    "fundamental": "رأي محلل الأخبار",
                    "risk": "نسبة ثقة مدير المخاطر (0-100%)",
                    "final_direction": "شراء/بيع/انتظار",
                    "trade_duration": "زمن الصفقة بالدقائق"
                }}
                """
                response = model.generate_content(prompt)
                clean_json = re.sub(r'```json\n|\n```', '', response.text).strip()
                res = json.loads(clean_json)
                
                col1, col2, col3 = st.columns(3)
                col1.info(f"📊 الفني:\n{res['technical']}")
                col2.warning(f"📰 الأخبار:\n{res['fundamental']}")
                col3.success(f"🛡️ المخاطر: {res['risk']}")
                
                st.markdown(f"### القرار النهائي: **{res['final_direction']}** | المدة: **{res['trade_duration']}**")
                    
            except Exception as e:
                st.error(f"خطأ: {e}")

with tab_chat:
    st.subheader("المساعد الشخصي (مع دعم الصور)")
    
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
                    if uploaded_file:
                        img = Image.open(uploaded_file)
                        response = model.generate_content([f"أنت متداول محترف. حلل الصورة. السياق: السعر {current_price}. سؤال: {prompt}", img])
                    else:
                        response = model.generate_content(f"أنت متداول محترف. السعر الحالي: {current_price}. أجب: {prompt}")
                    
                    st.markdown(response.text)
                    st.session_state.messages.append({"role": "assistant", "content": response.text})
                except Exception as e:
                    st.error(f"خطأ: {e}")
