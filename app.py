import streamlit as st
import pandas as pd
import yfinance as yf
from streamlit_lightweight_charts import renderLightweightCharts

st.set_page_config(layout="wide", page_title="Thunder Chart")
st.title("⚡ Thunder - MT4 Chart Test")

# جلب البيانات
@st.cache_data(ttl=60)
def get_data():
    df = yf.download("USDJPY=X", period="1mo", interval="1h")
    df.reset_index(inplace=True)
    df.rename(columns={'Datetime': 'time', 'Open': 'open', 'High': 'high', 'Low': 'low', 'Close': 'close'}, inplace=True)
    df['time'] = df['time'].dt.strftime('%Y-%m-%d %H:%M:%S')
    return df

try:
    df = get_data()
    
    # إعدادات الشارت
    chartOptions = {
        "layout": {"textColor": '#d1d4dc', "background": {"type": 'solid', "color": '#0a0a0f'}},
        "grid": {"vertLines": {"color": '#2B2B43'}, "horzLines": {"color": '#2B2B43'}},
        "timeScale": {"timeVisible": True, "borderColor": '#485c7b'},
    }

    # الشموع
    candlestickSeries = [{
        "type": 'Candlestick',
        "data": df[['time', 'open', 'high', 'low', 'close']].to_dict('records'),
        "options": {"upColor": '#26a69a', "downColor": '#ef5350', "borderVisible": False}
    }]

    renderLightweightCharts([{"chart": chartOptions, "series": candlestickSeries}], 'chart1')

except Exception as e:
    st.error(f"Error loading data: {e}")
