import streamlit as st
import pandas as pd
import yfinance as yf
import traceback

st.set_page_config(layout="wide", page_title="Thunder Chart")
st.title("⚡ Thunder - MT4 Chart Test")

# محاولة استيراد مكتبة الرسم
try:
    from streamlit_lightweight_charts import renderLightweightCharts
except Exception as e:
    st.error(f"مشكلة في تحميل مكتبة الرسم: {e}")
    st.stop()

try:
    # جلب البيانات مع تجاهل التعديلات التلقائية
    df = yf.download("USDJPY=X", period="1mo", interval="1h", auto_adjust=True)
    
    if df.empty:
        st.warning("لم يتم العثور على بيانات. قد يكون السوق مغلقاً أو ياهو فاينانس يواجه مشكلة.")
        st.stop()

    # إصلاح مشكلة الأعمدة
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
        
    df.reset_index(inplace=True)
    
    # تحديد اسم عمود الوقت (قد يكون Datetime أو Date)
    time_col = 'Datetime' if 'Datetime' in df.columns else 'Date'
    if time_col not in df.columns:
        st.error(f"لم أجد عمود الوقت. الأعمدة المتاحة هي: {df.columns}")
        st.stop()

    df = df[[time_col, 'Open', 'High', 'Low', 'Close']]
    df.columns = ['time', 'open', 'high', 'low', 'close']
    
    df['time'] = pd.to_datetime(df['time']).dt.strftime('%Y-%m-%d %H:%M:%S')
    
    # إعدادات الرسم
    chartOptions = {
        "layout": {"textColor": '#d1d4dc', "background": {"type": 'solid', "color": '#0a0a0f'}},
        "grid": {"vertLines": {"color": '#2B2B43'}, "horzLines": {'color': '#2B2B43'}},
        "timeScale": {"timeVisible": True, "borderColor": '#485c7b'},
    }

    candlestickSeries = [{
        "type": 'Candlestick',
        "data": df.to_dict('records'), 
        "options": {"upColor": '#26a69a', "downColor": '#ef5350', "borderVisible": False}
    }]

    renderLightweightCharts([{"chart": chartOptions, "series": candlestickSeries}], 'chart1')

except Exception as e:
    # هذا الجزء سيطبع الخطأ الحقيقي على الشاشة
    st.error(f"حدث خطأ تقني: {e}")
    st.code(traceback.format_exc())
