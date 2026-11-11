import streamlit as st
import pandas as pd
import yfinance as yf
import time
import numpy as np
from streamlit_lightweight_charts import renderLightweightCharts

# إعدادات الصفحة (وضع عريض وإخفاء القوائم)
st.set_page_config(layout="wide", page_title="Thunder", initial_sidebar_state="collapsed")
st.markdown("""
    <style>
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;}
        .block-container {padding-top: 1rem; padding-bottom: 0rem;}
    </style>
""", unsafe_allow_html=True)

st.title("⚡ Thunder Chart")

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
    
    # حساب المتوسطات المتحركة (EMA)
    df['ema50'] = df['close'].ewm(span=50, adjust=False).mean()
    df['ema200'] = df['close'].ewm(span=200, adjust=False).mean()
    return df

try:
    df = get_data()
    
    # 1. إعدادات الرسم البياني
    chartOptions = {
        "height": 500, # ارتفاع الرسم
        "layout": {"textColor": '#d1d4dc', "background": {"type": 'solid', "color": '#0a0a0f'}},
        "grid": {"vertLines": {"color": '#1e1e2d'}, "horzLines": {"color": '#1e1e2d'}},
        "timeScale": {"timeVisible": True, "borderColor": '#2B2B43'},
        "rightPriceScale": {"borderColor": '#2B2B43'},
        "handleScroll": True,
        "handleScale": True
    }

    # 2. سلسلة الشموع
    candlestickSeries = [{
        "type": 'Candlestick',
        "data": df[['time', 'open', 'high', 'low', 'close']].to_dict('records'), 
        "options": {"upColor": '#26a69a', "downColor": '#ef5350', "borderVisible": False}
    }]
    
    # 3. سلسلة المتوسط المتحرك 50
    ema50Series = [{
        "type": 'Line',
        "data": df[['time', 'ema50']].rename(columns={'ema50': 'value'}).to_dict('records'),
        "options": {"color": '#f59e0b', "lineWidth": 2, "title": "EMA 50"}
    }]
    
    # 4. سلسلة المتوسط المتحرك 200
    ema200Series = [{
        "type": 'Line',
        "data": df[['time', 'ema200']].rename(columns={'ema200': 'value'}).to_dict('records'),
        "options": {"color": '#3b82f6', "lineWidth": 2, "title": "EMA 200"}
    }]

    # دمج كل السلاسل في الرسم
    chart_data = [{
        "chart": chartOptions,
        "series": candlestickSeries + ema50Series + ema200Series
    }]
    
    renderLightweightCharts(chart_data, 'chart1')

except Exception as e:
    st.error(f"Error: {e}")
