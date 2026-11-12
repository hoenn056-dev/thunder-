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
st.title("⚡ Thunder - Institutional Trading System")

# ================= 1. إعداد الذكاء الاصطناعي =================
try:
    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=st.secrets["OPENROUTER_API_KEY"],
    )
    # النموذج الأساسي (مستقر حالياً ويدعم الصور)
    PRIMARY_MODEL = "google/gemma-4-31b-it:free"
    # النموذج الاحتياطي (راوتر تلقائي يختار نموذجاً مجانياً مناسباً)
    FALLBACK_MODEL = "openrouter/free"
except Exception as e:
    st.error(f"خطأ في مفتاح OpenRouter: {e}")

def safe_generate(**kwargs):
    """دالة محمية: تجرب النموذج الأساسي، وإذا فشل تنتقل للاحتياطي"""
    try:
        return client.chat.completions.create(model=PRIMARY_MODEL, **kwargs)
    except Exception as e:
        error_msg = str(e)
        if "404" in error_msg or "not found" in error_msg.lower():
            st.warning(f"النموذج {PRIMARY_MODEL} غير متاح، جاري التحويل إلى النموذج الاحتياطي...")
            try:
                return client.chat.completions.create(model=FALLBACK_MODEL, **kwargs)
            except Exception as fallback_err:
                raise Exception(f"فشل النموذج الأساسي والاحتياطي: {fallback_err}")
        elif "429" in error_msg:
            st.warning("تم الوصول للحد اليومي، جاري إعادة المحاولة...")
            time.sleep(5)
            return safe_generate(**kwargs) # إعادة المحاولة
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
    st.error("تعذر جلب البيانات.")
    st.stop()

last_candle = df.iloc[-1]
current_price = float(last_candle['close'])

# ================= 4. التبويبات =================
tab_chart, tab_trade, tab_chat = st.tabs(["📈 الشارت", "🎯 خطة التداول الذكية", "💬 الدردشة"])

with tab_chart:
    chart_df = df.reset_index()
    time_col = 'Datetime' if 'Datetime' in chart_df.columns else 'Date'
    chart_df['time'] = pd.to_datetime(chart_df[time_col]).apply(lambda x: int(time.mktime(x.timetuple())))
    
    candles = [{"type": 'Candlestick', "data": chart_df[['time', 'open', 'high', 'low', 'close']].dropna().to_dict('records'), "options": {"upColor": '#26a69a', "downColor": '#ef5350'}}]
    ema = [{"type": 'Line', "data": chart_df[['time', 'ema50']].dropna().rename(columns={'ema50': 'value'}).to_dict('records'), "options": {"color": '#f59e0b', "lineWidth": 2}}]
    
    chartOptions = {"height": 500, "layout": {"textColor": '#d1d4dc', "background": {"type": 'solid', "color": '#0a0a0f'}}, "grid": {"vertLines": {"color": '#1e1e2d'}, "horzLines": {"color": '#1e1e2d'}}, "timeScale": {"timeVisible": True}, "handleScroll": True, "handleScale": True}
    renderLightweightCharts([{"chart": chartOptions, "series": candles + ema}], 'chart1')

with tab_trade:
    st.subheader("خطة التداول (تحليل السيناريوهات)")
    
    if st.button("⚡ توليد خطة التداول الآن", use_container_width=True):
        with st.spinner("جاري تحليل السيناريوهات..."):
            try:
                recent_data = df.tail(5)[['open', 'high', 'low', 'close', 'rsi', 'ema50', 'atr']].to_string()
                
                prompt = f"""
                أنت متداول مؤسسي خبير. حلل البيانات التالية لزوج {symbol} على إطار {timeframe}.
                البيانات:
                {recent_data}
                السعر الحالي: {current_price:.3f}
                المنصة: {platform}.
                
                المطلوب: تحليل شامل مع سيناريوهات متعددة. أريد الإجابة بصيغة JSON فقط:
                {{
                    "scenarios": [
                        {{"type": "صعودي", "probability": "نسبة مئوية", "reasoning": "السبب"}},
                        {{"type": "هبوطي", "probability": "نسبة مئوية", "reasoning": "السبب"}}
                    ],
                    "final_decision": {{
                        "direction": "شراء" أو "بيع" أو "انتظار",
                        "entry_price": "سعر الدخول",
                        "tp": "هدف الربح",
                        "sl": "وقف الخسارة",
                        "trade_duration": "زمن الصفقة بالدقائق",
                        "confidence": "نسبة الثقة"
                    }},
                    "summary": "ملخص تنفيذي"
                }}
                """
                
                response = safe_generate(
                    messages=[{"role": "user", "content": prompt}],
                    response_format={"type": "json_object"},
                    temperature=0.2
                )
                
                plan = json.loads(response.choices[0].message.content)
                
                st.markdown("### 🔮 تحليل السيناريوهات")
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
                
                msg = f"⚡ *Thunder Trade Plan* ⚡\nالزوج: {symbol} ({timeframe})\nالقرار: {final.get('direction')} (ثقة {final.get('confidence')}%)\nالدخول: {final.get('entry_price')}\nالهدف: {final.get('tp')}\nالوقف: {final.get('sl')}\n*زمن الصفقة:* {final.get('trade_duration')}\n\n*الملخص:* {plan.get('summary')}"
                if send_telegram_alert(msg):
                    st.toast("📤 تم إرسال الخطة إلى تليجرام!")
                    
            except Exception as e:
                st.error(f"حدث خطأ في التحليل: {e}")

with tab_chat:
    st.subheader("المساعد الشخصي (مع دعم الصور)")
    
    if "messages" not in st.session_state:
        st.session_state.messages = []

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    uploaded_file = st.file_uploader("ارفع صورة شارت لتحليلها:", type=["png", "jpg", "jpeg"])

    if prompt := st.chat_input("اسأل Thunder..."):
        user_msg = {"role": "user", "content": prompt}
        st.session_state.messages.append(user_msg)
        
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("جاري التحليل..."):
                try:
                    messages = [{"role": "user", "content": f"أنت متداول محترف. السعر الحالي: {current_price}. أجب: {prompt}"}]
                    
                    if uploaded_file:
                        img = Image.open(uploaded_file)
                        buffered = BytesIO()
                        img.save(buffered, format="JPEG")
                        base64_image = base64.b64encode(buffered.getvalue()).decode("utf-8")
                        
                        messages = [{
                            "role": "user",
                            "content": [
                                {"type": "text", "text": f"أنت متداول محترف. حلل الصورة. السعر: {current_price}. سؤال: {prompt}"},
                                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                            ]
                        }]

                    response = safe_generate(
                        messages=messages,
                        temperature=0.5
                    )
                    
                    st.markdown(response.choices[0].message.content)
                    st.session_state.messages.append({"role": "assistant", "content": response.choices[0].message.content})
                except Exception as e:
                    st.error(f"خطأ: {e}")
