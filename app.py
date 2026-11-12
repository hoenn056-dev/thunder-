import streamlit as st
import pandas as pd
import yfinance as yf
import time
import requests
import pandas_ta_classic as ta
from openai import OpenAI
from streamlit_lightweight_charts import renderLightweightCharts
from PIL import Image
import json
import base64
from io import BytesIO

st.set_page_config(layout="wide", page_title="Thunder Pro", initial_sidebar_state="expanded")
st.markdown("""<style>#MainMenu {visibility: hidden;} footer {visibility: hidden;} .block-container {padding-top: 1rem;}</style>""", unsafe_allow_html=True)
st.title("⚡ Thunder - Precision Scalping System")

# ================= 1. إعداد الذكاء الاصطناعي =================
try:
    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=st.secrets["OPENROUTER_API_KEY"],
    )
    PRIMARY_MODEL = "google/gemma-4-31b-it:free"
    FALLBACK_MODEL = "openrouter/free"
except Exception as e:
    st.error(f"خطأ في مفتاح OpenRouter: {e}")

def safe_generate(**kwargs):
    try:
        return client.chat.completions.create(model=PRIMARY_MODEL, **kwargs)
    except Exception as e:
        error_msg = str(e)
        if "404" in error_msg or "not found" in error_msg.lower():
            st.warning("النموذج الأساسي غير متاح، جاري التحويل إلى النموذج الاحتياطي...")
            return client.chat.completions.create(model=FALLBACK_MODEL, **kwargs)
        elif "429" in error_msg:
            st.warning("تم الوصول للحد اليومي، جاري إعادة المحاولة...")
            time.sleep(5)
            return safe_generate(**kwargs)
        else:
            raise e

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
    platform = st.radio("اختر المنصة:", ["Pocket Option (Binary)", "تداول فوركس (Scalping)"])
    symbol = st.selectbox("اختر الزوج", ["USD/JPY", "EUR/USD", "GBP/USD", "AUD/USD"])
    
    # نثبت الإطار الزمني للاتجاه العام
    timeframe = st.selectbox("الإطار الزمني الرئيسي (للاتجاه)", ["15m", "1h"], index=0)
    yf_symbol = symbol.replace("/", "") + "=X"

# ================= 3. جلب البيانات (متعدد الأطر) =================
@st.cache_data(ttl=60)
def get_market_data(sym, main_tf):
    # 1. جلب الإطار الرئيسي (15m)
    period = "5d" if main_tf == "15m" else "1mo"
    df_main = yf.download(sym, period=period, interval=main_tf, auto_adjust=True, progress=False)
    
    # 2. جلب إطار الدخول السريع (5m)
    df_entry = yf.download(sym, period="5d", interval="5m", auto_adjust=True, progress=False)
    
    if df_main.empty or df_entry.empty: return None, None
    
    for df in [df_main, df_entry]:
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        df.columns = [c.lower() for c in df.columns]
        df['rsi'] = ta.rsi(df['close'], length=14)
        df['ema50'] = ta.ema(df['close'], length=50)
        df['atr'] = ta.atr(df['high'], df['low'], df['close'], length=14)
        
    return df_main, df_entry

df_main, df_entry = get_market_data(yf_symbol, timeframe)

if df_main is None or df_entry is None or len(df_main) < 20:
    st.error("تعذر جلب البيانات.")
    st.stop()

current_price = float(df_entry.iloc[-1]['close'])

# ================= 4. التبويبات =================
tab_chart, tab_trade, tab_chat = st.tabs(["📈 الشارت", "🎯 خطة التداول الذكية", "💬 الدردشة"])

with tab_chart:
    chart_df = df_main.reset_index()
    time_col = 'Datetime' if 'Datetime' in chart_df.columns else 'Date'
    chart_df['time'] = pd.to_datetime(chart_df[time_col]).apply(lambda x: int(time.mktime(x.timetuple())))
    
    candles = [{"type": 'Candlestick', "data": chart_df[['time', 'open', 'high', 'low', 'close']].dropna().to_dict('records'), "options": {"upColor": '#26a69a', "downColor": '#ef5350'}}]
    ema = [{"type": 'Line', "data": chart_df[['time', 'ema50']].dropna().rename(columns={'ema50': 'value'}).to_dict('records'), "options": {"color": '#f59e0b', "lineWidth": 2}}]
    
    chartOptions = {"height": 500, "layout": {"textColor": '#d1d4dc', "background": {"type": 'solid', "color": '#0a0a0f'}}, "grid": {"vertLines": {"color": '#1e1e2d'}, "horzLines": {"color": '#1e1e2d'}}, "timeScale": {"timeVisible": True}, "handleScroll": True, "handleScale": True}
    renderLightweightCharts([{"chart": chartOptions, "series": candles + ema}], 'chart1')

with tab_trade:
    st.subheader("خطة التداول (دقة عالية - 5m/15m)")
    
    if st.button("⚡ توليد خطة تداول سريعة الآن", use_container_width=True):
        with st.spinner("جاري التحليل الفني المتقدم (15m + 5m)..."):
            try:
                # تجهيز البيانات للإطارين
                data_15m = df_main.tail(3)[['open', 'high', 'low', 'close', 'rsi', 'ema50', 'atr']].to_string()
                data_5m = df_entry.tail(3)[['open', 'high', 'low', 'close', 'rsi', 'ema50']].to_string()
                
                # تعليمات صارمة جداً للذكاء الاصطناعي
                prompt = f"""
                أنت متداول سكالبينج محترف (Pro Scalper) تعمل على منصة Pocket Option. 
                مهمتك هي إعطاء صفقة دقيقة جداً، عالية الربح، وذات زمن قصير جداً.
                
                البيانات الحالية لزوج {symbol}:
                السعر الحالي: {current_price:.3f}
                
                1. إطار 15 دقيقة (لتحديد الاتجاه العام):
                {data_15m}
                
                2. إطار 5 دقائق (لتحديد نقطة الدخول الدقيقة):
                {data_5m}
                
                القواعد الصارمة:
                - زمن الصفقة (trade_duration) يجب أن يكون "15 دقيقة" أو "5 دقائق" فقط. لا تقبل بأكثر من ذلك.
                - يجب أن يكون هناك توافق (Confluence) بين إشارة 5 دقائق واتجاه 15 دقيقة.
                - هدف الربح (TP) ووقف الخسارة (SL) يجب أن يكونا قريبين جداً من السعر (Scalping).
                - أريد الإجابة بصيغة JSON فقط:
                {{
                    "scenarios": [
                        {{"type": "صعودي", "probability": "نسبة مئوية", "reasoning": "السبب"}},
                        {{"type": "هبوطي", "probability": "نسبة مئوية", "reasoning": "السبب"}}
                    ],
                    "final_decision": {{
                        "direction": "شراء" أو "بيع" أو "انتظار",
                        "entry_price": "{current_price:.3f}",
                        "tp": "هدف الربح (قريب جداً)",
                        "sl": "وقف الخسارة (قريب جداً)",
                        "trade_duration": "15 دقيقة", 
                        "confidence": "نسبة الثقة (يجب أن تكون عالية)"
                    }},
                    "summary": "ملخص تنفيذي دقيق جداً يشرح لماذا هذه الصفقة ستربح سريعاً"
                }}
                """
                
                response = safe_generate(
                    messages=[{"role": "user", "content": prompt}],
                    response_format={"type": "json_object"},
                    temperature=0.1 # تقليل الإبداع لصالح الدقة
                )
                
                plan = json.loads(response.choices[0].message.content)
                
                st.markdown("### 🔮 تحليل السيناريوهات (5m/15m)")
                for scenario in plan.get('scenarios', []):
                    with st.expander(f"سيناريو {scenario.get('type')} (الاحتمالية: {scenario.get('probability')})"):
                        st.write(scenario.get('reasoning'))
                
                st.divider()
                
                final = plan.get('final_decision', {})
                st.markdown(f"### 🎯 القرار النهائي: **{final.get('direction')}** (الثقة: {final.get('confidence')}%)")
                
                c1, c2, c3, c4 = st.columns(4)
                c1.info(f"**نقطة الدخول**\n\n### {final.get('entry_price')}")
                c2.success(f"**هدف الربح**\n\n### {final.get('tp')}")
                c3.error(f"**وقف الخسارة**\n\n### {final.get('sl')}")
                c4.warning(f"**زمن الصفقة**\n\n### {final.get('trade_duration')}")
                
                st.info(f"**الملخص:** {plan.get('summary')}")
                
                # إرسال إلى تليجرام
                msg = f"⚡ *Thunder Scalping Plan* ⚡\nالزوج: {symbol}\nالقرار: {final.get('direction')} (ثقة {final.get('confidence')}%)\nالدخول: {final.get('entry_price')}\nالهدف: {final.get('tp')}\nالوقف: {final.get('sl')}\n*زمن الصفقة:* {final.get('trade_duration')}\n\n*الملخص:* {plan.get('summary')}"
                if send_telegram_alert(msg):
                    st.toast("📤 تم إرسال الخطة إلى تليجرام!")
                    
            except Exception as e:
                st.error(f"حدث خطأ في التحليل: {e}")

with tab_chat:
    st.subheader("المساعد الشخصي")
    
    if "messages" not in st.session_state:
        st.session_state.messages = []

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if prompt := st.chat_input("اسأل Thunder..."):
        user_msg = {"role": "user", "content": prompt}
        st.session_state.messages.append(user_msg)
        
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("جاري التحليل..."):
                try:
                    full_prompt = f"أنت متداول محترف. السعر الحالي: {current_price}. أجب بالعربية: {prompt}"
                    response = safe_generate(
                        messages=[{"role": "user", "content": full_prompt}],
                        temperature=0.5
                    )
                    
                    st.markdown(response.choices[0].message.content)
                    st.session_state.messages.append({"role": "assistant", "content": response.choices[0].message.content})
                except Exception as e:
                    st.error(f"خطأ: {e}")
