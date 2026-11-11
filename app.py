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
st.title("⚡ Thunder - Institutional Trading Dashboard")

# ================= 1. إعدادات الذكاء الاصطناعي وتليجرام =================
try:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    # نستخدم نموذج Pro لتحليل الصور العميق (إذا لم يكن متاحاً، سيستخدم Flash)
    try:
        model = genai.GenerativeModel('gemini-1.5-pro-latest')
    except:
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

# ================= 2. دالة الخلفية (للبحث عن الصفقات تلقائياً) =================
def background_scanner():
    # نطاق الأزواج التي سيتم فحصها في الخلفية
    pairs = ["USD/JPY", "EUR/USD", "GBP/USD", "AUD/USD"]
    
    while True:
        best_trade_msg = "🔍 *تحديث السوق التلقائي*\n"
        found_trade = False
        
        for pair in pairs:
            yf_sym = pair.replace("/", "") + "=X"
            try:
                df = yf.download(yf_sym, period="5d", interval="1h", auto_adjust=True, progress=False)
                if df.empty: continue
                
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)
                df.columns = [c.lower() for c in df.columns]
                
                # حساب مؤشرات سريعة
                df['rsi'] = ta.rsi(df['close'], length=14)
                df['ema50'] = ta.ema(df['close'], length=50)
                
                last = df.iloc[-1]
                price = last['close']
                
                # شرط الدخول (مثال: RSI أقل من 30 للشراء، أعلى من 70 للبيع)
                if last['rsi'] < 30 and price > last['ema50']:
                    best_trade_msg += f"\n🟢 *فرصة شراء*: {pair}\nالسعر: {price:.3f}\nRSI: {last['rsi']:.1f}\n"
                    found_trade = True
                elif last['rsi'] > 70 and price < last['ema50']:
                    best_trade_msg += f"\n🔴 *فرصة بيع*: {pair}\nالسعر: {price:.3f}\nRSI: {last['rsi']:.1f}\n"
                    found_trade = True
            except:
                pass
                
        # إرسال التنبيه إذا وجدنا فرصة
        if found_trade:
            send_telegram_alert(best_trade_msg)
            
        time.sleep(3600) # ينتظر ساعة ثم يعيد الفحص

# تشغيل الخلفية مرة واحدة فقط عند فتح التطبيق
if "scanner_started" not in st.session_state:
    st.session_state.scanner_started = True
    thread = threading.Thread(target=background_scanner, daemon=True)
    thread.start()

# ================= 3. دالة جلب البيانات للرسم البياني =================
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
    
    macd = ta.macd(df['close'])
    df['macd_line'] = macd['MACD_12_26_9']
    df['macd_signal'] = macd['MACDs_12_26_9']
    
    bb = ta.bbands(df['close'], length=20)
    df['bb_upper'] = bb['BBU_20_2.0']
    df['bb_lower'] = bb['BBL_20_2.0']
    
    return df

# ================= 4. الإعدادات الجانبية =================
with st.sidebar:
    st.header("إعدادات السوق")
    symbol = st.selectbox("اختر الزوج", ["USD/JPY", "EUR/USD", "GBP/USD", "AUD/USD", "USD/CAD"])
    timeframe = st.selectbox("الإطار الزمني", ["15m", "1h", "4h", "1d"], index=1)
    yf_symbol = symbol.replace("/", "") + "=X"

# جلب البيانات
df = get_market_data(yf_symbol, timeframe)

if df is None or len(df) < 50:
    st.error("تعذر جلب البيانات.")
    st.stop()

last_candle = df.iloc[-1]
current_price = float(last_candle['close'])
atr_value = float(last_candle['atr']) if not pd.isna(last_candle['atr']) else 0.1

# ================= 5. التبويبات =================
tab_chart, tab_trade, tab_chat = st.tabs(["📈 شارت TradingView", "🎯 خطة التداول", "🤖 المحلل الذكي (مع صور)"])

with tab_chart:
    chart_df = df.reset_index()
    time_col = 'Datetime' if 'Datetime' in chart_df.columns else 'Date'
    chart_df['time'] = pd.to_datetime(chart_df[time_col]).apply(lambda x: int(time.mktime(x.timetuple())))
    
    candles = [{"type": 'Candlestick', "data": chart_df[['time', 'open', 'high', 'low', 'close']].dropna().to_dict('records'), "options": {"upColor": '#26a69a', "downColor": '#ef5350'}}]
    ema = [{"type": 'Line', "data": chart_df[['time', 'ema50']].dropna().rename(columns={'ema50': 'value'}).to_dict('records'), "options": {"color": '#f59e0b', "lineWidth": 2}}]
    bb_upper = [{"type": 'Line', "data": chart_df[['time', 'bb_upper']].dropna().rename(columns={'bb_upper': 'value'}).to_dict('records'), "options": {"color": '#3b82f6', "lineWidth": 1, "lineStyle": 2}}]
    bb_lower = [{"type": 'Line', "data": chart_df[['time', 'bb_lower']].dropna().rename(columns={'bb_lower': 'value'}).to_dict('records'), "options": {"color": '#3b82f6', "lineWidth": 1, "lineStyle": 2}}]

    chartOptions = {"height": 500, "layout": {"textColor": '#d1d4dc', "background": {"type": 'solid', "color": '#0a0a0f'}}, "grid": {"vertLines": {"color": '#1e1e2d'}, "horzLines": {"color": '#1e1e2d'}}, "timeScale": {"timeVisible": True}, "handleScroll": True, "handleScale": True}
    renderLightweightCharts([{"chart": chartOptions, "series": candles + ema + bb_upper + bb_lower}], 'chart1')

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
    
    # تهيئة سجل المحادثة (لن يُمسح أبداً)
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # عرض الرسائل السابقة
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if "image" in message:
                st.image(message["image"])

    # أداة رفع الصور
    uploaded_file = st.file_uploader("ارفع صورة (شارت، رسم بياني، إلخ) لتحليلها:", type=["png", "jpg", "jpeg"])

    # إدخال النص
    if prompt := st.chat_input("اسأل Thunder..."):
        # إضافة رسالة المستخدم
        user_msg = {"role": "user", "content": prompt}
        st.session_state.messages.append(user_msg)
        with st.chat_message("user"):
            st.markdown(prompt)
            if uploaded_file:
                st.image(uploaded_file)

        # تجهيز الرد
        with st.chat_message("assistant"):
            with st.spinner("جاري التحليل..."):
                try:
                    # تجهيز السياق
                    context = f"السعر: {current_price:.3f}, RSI: {last_candle['rsi']:.1f}"
                    
                    # إذا كان هناك صورة، نرسلها للذكاء الاصطناعي
                    if uploaded_file:
                        img = Image.open(uploaded_file)
                        response = model.generate_content([
                            f"أنت متداول محترف. حلل هذه الصورة (شارت) باللغة العربية. السياق الحالي: {context}. سؤال المستخدم: {prompt}",
                            img
                        ])
                    else:
                        response = model.generate_content(f"أنت متداول محترف. السياق: {context}. أجب: {prompt}")
                    
                    st.markdown(response.text)
                    st.session_state.messages.append({"role": "assistant", "content": response.text})
                except Exception as e:
                    st.error(f"خطأ: {e}")
