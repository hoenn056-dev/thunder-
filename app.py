import streamlit as st
import pandas as pd
import yfinance as yf
import time
import requests
import pandas_ta_classic as ta
import google.generativeai as genai
from streamlit_lightweight_charts_pro import renderChart

st.set_page_config(layout="wide", page_title="Thunder Pro", initial_sidebar_state="expanded")
st.markdown("""<style>#MainMenu {visibility: hidden;} footer {visibility: hidden;} .block-container {padding-top: 1rem;}</style>""", unsafe_allow_html=True)
st.title("⚡ Thunder - Institutional TradingView Dashboard")

# ================= 1. الإعدادات الجانبية =================
with st.sidebar:
    st.header("إعدادات السوق")
    symbol = st.selectbox("اختر الزوج", ["USD/JPY", "EUR/USD", "GBP/USD", "AUD/USD", "USD/CAD"])
    timeframe = st.selectbox("الإطار الزمني", ["15m", "1h", "4h", "1d"], index=1)
    yf_symbol = symbol.replace("/", "") + "=X"

# ================= 2. دوال التحليل والبيانات =================
@st.cache_data(ttl=300)
def get_market_data(sym, tf):
    # تحديد فترة الجلب المناسبة لكل إطار (يمنع خطأ البيانات الفارغة)
    if tf == "15m":
        period = "5d"
    elif tf == "1h":
        period = "1mo"
    else:
        period = "3mo"

    df = yf.download(sym, period=period, interval=tf, auto_adjust=True)
    if df.empty: 
        return None
        
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    
    df.columns = [c.lower() for c in df.columns]
    
    # حساب المؤشرات الفنية
    df['rsi'] = ta.rsi(df['close'], length=14)
    df['ema50'] = ta.ema(df['close'], length=50)
    df['atr'] = ta.atr(df['high'], df['low'], df['close'], length=14)
    return df

def send_telegram_alert(text):
    try:
        token = st.secrets["TELEGRAM_TOKEN"]
        chat_id = st.secrets["TELEGRAM_CHAT_ID"]
        res = requests.post(f"https://api.telegram.org/bot{token}/sendMessage", 
                            json={"chat_id": chat_id, "text": text})
        return res.status_code == 200
    except:
        return False

# جلب البيانات
df = get_market_data(yf_symbol, timeframe)

if df is None or len(df) < 50:
    st.error("تعذر جلب البيانات الكافية لهذا الإطار الزمني. جرّب إطاراً زمنياً آخر أو تأكد من فتح السوق.")
    st.stop()

# استخراج قيم الشمعة الأخيرة
last_candle = df.iloc[-1]
current_price = float(last_candle['close'])
rsi_value = float(last_candle['rsi']) if not pd.isna(last_candle['rsi']) else 50.0
atr_value = float(last_candle['atr']) if not pd.isna(last_candle['atr']) else 0.1

# ================= 3. عرض المقاييس العلوية =================
col1, col2, col3, col4 = st.columns(4)
col1.metric("السعر الحالي", f"{current_price:.3f}")
col2.metric("مؤشر RSI (14)", f"{rsi_value:.1f}", delta="تشبع شراء" if rsi_value > 70 else "تشبع بيع" if rsi_value < 30 else "منطقة محايدة")
col3.metric("تقلب ATR", f"{atr_value:.3f}")
col4.metric("الإطار الزمني", timeframe.upper())

st.divider()

# ================= 4. التبويبات (الشارت وخطة التداول) =================
tab_chart, tab_trade = st.tabs(["📈 شارت TradingView الاحترافي", "🎯 خطة التداول والمخاطر"])

with tab_chart:
    # تجهيز البيانات لـ renderChart
    chart_df = df.reset_index()
    # تحويل عمود الوقت إلى تنسيق تفهمه المكتبة
    time_col = 'Datetime' if 'Datetime' in chart_df.columns else 'Date'
    chart_df['time'] = pd.to_datetime(chart_df[time_col])
    
    # استدعاء الدالة المبسطة renderChart
    renderChart(
        chart_df,
        title=f"{symbol} - {timeframe}",
        height=520,
        seriesType='candlestick',
        key="tradingview_chart"
    )

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
        msg = f"⚡ Thunder Alert ⚡\n\nالزوج: {symbol} ({timeframe})\nالاتجاه: {direction}\nالدخول: {current_price:.3f}\nالهدف: {tp:.3f}\nوقف الخسارة: {sl:.3f}"
        if send_telegram_alert(msg):
            st.success("تم إرسال التنبيه إلى تليجرام بنجاح!")
        else:
            st.error("تعذر الإرسال، تأكد من إعدادات البوت.")
