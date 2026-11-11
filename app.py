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
    
    st.divider()
    st.info("💡 **Thunder** يقرأ كافة المؤشرات (MACD, BB, StochRSI, VWAP) ليعطيك تحليلاً عميقاً.")

# ================= 2. إعداد الذكاء الاصطناعي =================
try:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    # نستخدم أحدث نموذج للتحليل العميق
    model = genai.GenerativeModel('gemini-flash-latest')
except Exception as e:
    st.error(f"خطأ في مفتاح Gemini: {e}")

def send_telegram_alert(text):
    try:
        token = st.secrets["TELEGRAM_TOKEN"]
        chat_id = st.secrets["TELEGRAM_CHAT_ID"]
        res = requests.post(f"https://api.telegram.org/bot{token}/sendMessage", 
                            json={"chat_id": chat_id, "text": text})
        return res.status_code == 200
    except:
        return False

# ================= 3. محرك البيانات والمؤشرات =================
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
    
    # حساب المؤشرات الفنية الاحترافية
    df['rsi'] = ta.rsi(df['close'], length=14)
    df['ema50'] = ta.ema(df['close'], length=50)
    df['atr'] = ta.atr(df['high'], df['low'], df['close'], length=14)
    
    macd = ta.macd(df['close'])
    df['macd_line'] = macd['MACD_12_26_9']
    df['macd_signal'] = macd['MACDs_12_26_9']
    df['macd_hist'] = macd['MACDh_12_26_9']
    
    bb = ta.bbands(df['close'], length=20)
    df['bb_upper'] = bb['BBU_20_2.0']
    df['bb_lower'] = bb['BBL_20_2.0']
    
    df['stochrsi'] = ta.stochrsi(df['close'])['STOCHRSIk_14_14_3_3']
    
    # VWAP يحتاج إلى بيانات الحجم، ياهو فاينانس قد لا يوفرها للفوركس، لذا نستخدمه بحذر
    try:
        df['vwap'] = ta.vwap(df['high'], df['low'], df['close'], df['volume'])
    except:
        df['vwap'] = df['close'] # fallback
    
    return df

# جلب البيانات
df = get_market_data(yf_symbol, timeframe)

if df is None or len(df) < 50:
    st.error("تعذر جلب البيانات. جرب إطاراً زمنياً آخر.")
    st.stop()

last_candle = df.iloc[-1]
current_price = float(last_candle['close'])
atr_value = float(last_candle['atr']) if not pd.isna(last_candle['atr']) else 0.1

# ================= 4. المقاييس العلوية =================
col1, col2, col3, col4 = st.columns(4)
col1.metric("السعر الحالي", f"{current_price:.3f}")
col2.metric("RSI", f"{last_candle['rsi']:.1f}", delta="تشبع شراء" if last_candle['rsi'] > 70 else "تشبع بيع" if last_candle['rsi'] < 30 else "محايد")
col3.metric("StochRSI", f"{last_candle['stochrsi']:.1f}")
col4.metric("الإطار", timeframe.upper())

st.divider()

# ================= 5. التبويبات =================
tab_chart, tab_trade, tab_chat = st.tabs(["📈 شارت TradingView", "🎯 خطة التداول", "🤖 المحلل الذكي العميق"])

with tab_chart:
    chart_df = df.reset_index()
    time_col = 'Datetime' if 'Datetime' in chart_df.columns else 'Date'
    chart_df['time'] = pd.to_datetime(chart_df[time_col]).apply(lambda x: int(time.mktime(x.timetuple())))
    
    # الشموع
    candles = [{"type": 'Candlestick', "data": chart_df[['time', 'open', 'high', 'low', 'close']].dropna().to_dict('records'), "options": {"upColor": '#26a69a', "downColor": '#ef5350', "borderVisible": False}}]
    
    # المتوسط المتحرك
    ema_data = chart_df[['time', 'ema50']].dropna().rename(columns={'ema50': 'value'})
    ema = [{"type": 'Line', "data": ema_data.to_dict('records'), "options": {"color": '#f59e0b', "lineWidth": 2}}]
    
    # البولينجر باند
    bb_upper = chart_df[['time', 'bb_upper']].dropna().rename(columns={'bb_upper': 'value'})
    bb_lower = chart_df[['time', 'bb_lower']].dropna().rename(columns={'bb_lower': 'value'})
    bb_series = [
        {"type": 'Line', "data": bb_upper.to_dict('records'), "options": {"color": '#3b82f6', "lineWidth": 1, "lineStyle": 2}},
        {"type": 'Line', "data": bb_lower.to_dict('records'), "options": {"color": '#3b82f6', "lineWidth": 1, "lineStyle": 2}}
    ]

    chartOptions = {"height": 500, "layout": {"textColor": '#d1d4dc', "background": {"type": 'solid', "color": '#0a0a0f'}}, "grid": {"vertLines": {"color": '#1e1e2d'}, "horzLines": {"color": '#1e1e2d'}}, "timeScale": {"timeVisible": True}, "handleScroll": True, "handleScale": True}
    
    renderLightweightCharts([{"chart": chartOptions, "series": candles + ema + bb_series}], 'chart1')

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
    st.subheader("المحلل المؤسسي (Deep Analysis)")
    
    if "messages" not in st.session_state:
        st.session_state.messages = []

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if prompt := st.chat_input("اسأل Thunder..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("جاري التحليل العميق وربط المؤشرات..."):
                try:
                    # تجهيز بيانات غنية جداً للذكاء الاصطناعي (آخر 3 شموع مع كل المؤشرات)
                    recent_candles = df.tail(3)[['open', 'high', 'low', 'close', 'rsi', 'macd_line', 'macd_signal', 'bb_upper', 'bb_lower', 'stochrsi']].to_string()
                    
                    full_context = f"""
                    أنت كبير متداولي الكم (Senior Quant Trader). مهمتك تحليل البيانات التالية بعمق شديد وربط المؤشرات (Confluence) قبل الإجابة.
                    
                    البيانات الحالية:
                    الزوج: {symbol} | الإطار الزمني: {timeframe}
                    السعر الحالي: {current_price:.3f}
                    
                    آخر 3 شموع مع المؤشرات:
                    {recent_candles}
                    
                    خطة التداول المقترحة آلياً: اتجاه {direction}، دخول {current_price:.3f}، هدف {tp:.3f}، وقف {sl:.3f}.
                    
                    سؤال المستخدم: {prompt}
                    
                    أجب باللغة العربية، كن دقيقاً، اشرح أسبابك بناءً على تقاطعات المؤشرات، ولا تعطي إجابة سطحية.
                    """
                    
                    # طلب التحليل (بدون تحديد thinking_level ليعطي النموذج كل قوته)
                    response = model.generate_content(full_context)
                    
                    st.markdown(response.text)
                    st.session_state.messages.append({"role": "assistant", "content": response.text})
                except Exception as e:
                    st.error(f"خطأ: {e}")
