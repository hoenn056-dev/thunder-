import streamlit as st
import pandas as pd
import yfinance as yf
import time
import google.generativeai as genai
from streamlit_lightweight_charts import renderLightweightCharts

# إعدادات الصفحة
st.set_page_config(layout="wide", page_title="Thunder AI", initial_sidebar_state="collapsed")
st.markdown("""
    <style>
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;}
        .block-container {padding-top: 1rem; padding-bottom: 0rem;}
    </style>
""", unsafe_allow_html=True)

st.title("⚡ Thunder - AI Analyst")

# إعداد الذكاء الاصطناعي
try:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    model = genai.GenerativeModel('gemini-1.5-flash')
except Exception as e:
    st.error(f"خطأ في إعداد مفتاح Gemini: {e}. تأكد من إضافته في إعدادات Secrets.")

# جلب البيانات
@st.cache_data(ttl=60)
def get_data():
    df = yf.download("USDJPY=X", period="6mo", interval="1h", auto_adjust=True)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df.reset_index(inplace=True)
    time_col = 'Datetime' if 'Datetime' in df.columns else 'Date'
    df['time'] = pd.to_datetime(df[time_col]).apply(lambda x: int(time.mktime(x.timetuple())))
    df = df[['time', 'Open', 'High', 'Low', 'Close']].copy()
    df.columns = ['time', 'open', 'high', 'low', 'close']
    df['ema50'] = df['close'].ewm(span=50, adjust=False).mean()
    df['ema200'] = df['close'].ewm(span=200, adjust=False).mean()
    return df

df = get_data()
current_price = df['close'].iloc[-1]

# إنشاء تبويبات
tab_chart, tab_chat = st.tabs(["📈 الرسم البياني", "🤖 المحلل الذكي"])

# --- التبويب الأول: الرسم البياني ---
with tab_chart:
    chartOptions = {
        "height": 500,
        "layout": {"textColor": '#d1d4dc', "background": {"type": 'solid', "color": '#0a0a0f'}},
        "grid": {"vertLines": {"color": '#1e1e2d'}, "horzLines": {"color": '#1e1e2d'}},
        "timeScale": {"timeVisible": True, "borderColor": '#2B2B43'},
        "rightPriceScale": {"borderColor": '#2B2B43'},
        "handleScroll": True,
        "handleScale": True
    }

    candlestickSeries = [{"type": 'Candlestick', "data": df[['time', 'open', 'high', 'low', 'close']].to_dict('records'), "options": {"upColor": '#26a69a', "downColor": '#ef5350', "borderVisible": False}}]
    ema50Series = [{"type": 'Line', "data": df[['time', 'ema50']].rename(columns={'ema50': 'value'}).to_dict('records'), "options": {"color": '#f59e0b', "lineWidth": 2, "title": "EMA 50"}}]
    ema200Series = [{"type": 'Line', "data": df[['time', 'ema200']].rename(columns={'ema200': 'value'}).to_dict('records'), "options": {"color": '#3b82f6', "lineWidth": 2, "title": "EMA 200"}}]

    renderLightweightCharts([{"chart": chartOptions, "series": candlestickSeries + ema50Series + ema200Series}], 'chart1')

# --- التبويب الثاني: المحادثة الذكية ---
with tab_chat:
    st.markdown(f"**السعر الحالي لـ USD/JPY:** `{current_price:.3f}`")
    
    # تهيئة سجل المحادثة
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # عرض الرسائل السابقة
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # إدخال سؤال جديد
    if prompt := st.chat_input("اسأل Thunder عن التحليل..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # تجهيز السياق للذكاء الاصطناعي
        context = f"Current Price: {current_price:.3f}\nLast 3 candles:\n{df.tail(3).to_string()}"
        
        # طلب الإجابة
        with st.chat_message("assistant"):
            with st.spinner("جاري تحليل السوق..."):
                try:
                    response = model.generate_content(
                        f"You are a professional financial analyst. Here is the recent market data for USD/JPY: \n{context}\n\nAnswer the user's question accurately in Arabic: {prompt}"
                    )
                    st.markdown(response.text)
                    st.session_state.messages.append({"role": "assistant", "content": response.text})
                except Exception as e:
                    st.error(f"حدث خطأ: {e}")
