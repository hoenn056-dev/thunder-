import streamlit as st
import pandas as pd
import yfinance as yf
import time
from streamlit_lightweight_charts import renderLightweightCharts

st.set_page_config(layout="wide", page_title="Thunder Chart")
st.title("⚡ Thunder - MT4 Chart")
st.write("💡 **نصيحة:** اضغط على الرسم البياني بإصبعك، ثم اسحبه يميناً أو يساراً، واستخدم إصبعين للتكبير.")

# زر لتحديث البيانات (لجلب شموع جديدة)
if st.button("🔄 تحديث البيانات الحية"):
    st.cache_data.clear() # مسح الذاكرة المؤقتة لجلب أحدث الأسعار

@st.cache_data(ttl=60) # تحديث كل دقيقة
def get_data():
    # جلب البيانات اللحظية
    df = yf.download("USDJPY=X", period="1mo", interval="1h", auto_adjust=True)
    
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
        
    df.reset_index(inplace=True)
    time_col = 'Datetime' if 'Datetime' in df.columns else 'Date'
    
    # تحويل الوقت إلى Unix Timestamp (بالثواني)
    df['time'] = pd.to_datetime(df[time_col]).apply(lambda x: int(time.mktime(x.timetuple())))
    
    df = df[['time', 'Open', 'High', 'Low', 'Close']]
    df.columns = ['time', 'open', 'high', 'low', 'close']
    return df

try:
    df = get_data()
    
    chartOptions = {
        "layout": {"textColor": '#d1d4dc', "background": {"type": 'solid', "color": '#0a0a0f'}},
        "grid": {"vertLines": {"color": '#2B2B43'}, "horzLines": {"color": '#2B2B43'}},
        "timeScale": {"timeVisible": True, "borderColor": '#485c7b'},
        "rightPriceScale": {"borderColor": '#485c7b'},
        # تفعيل السحب والتكبير بشكل صريح
        "handleScroll": True,
        "handleScale": True
    }

    candlestickSeries = [{
        "type": 'Candlestick',
        "data": df.to_dict('records'), 
        "options": {"upColor": '#26a69a', "downColor": '#ef5350', "borderVisible": False}
    }]

    renderLightweightCharts([{"chart": chartOptions, "series": candlestickSeries}], 'chart1')

except Exception as e:
    st.error(f"Error: {e}")
