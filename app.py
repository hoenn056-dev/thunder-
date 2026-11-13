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

st.set_page_config(layout="wide", page_title="Thunder Sniper Pro", initial_sidebar_state="expanded")
st.markdown("""<style>#MainMenu {visibility: hidden;} footer {visibility: hidden;} .block-container {padding-top: 1rem;}</style>""", unsafe_allow_html=True)
st.title("⚡ Thunder Sniper Pro (Liquidity Hunter)")

# ================= 1. إعداد الذكاء الاصطناعي =================
try:
    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=st.secrets["OPENROUTER_API_KEY"],
    )
    PRIMARY_MODEL = "deepseek/deepseek-v4.1-flash-1017"
    FALLBACK_MODEL = "meta-llama/llama-3-8b-instruct:free"
except Exception as e:
    st.error(f"خطأ في مفتاح OpenRouter: {e}")

def generate_analysis(prompt):
    try:
        response = client.chat.completions.create(
            model=PRIMARY_MODEL,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.1
        )
        return response.choices[0].message.content
    except Exception as e:
        try:
            response = client.chat.completions.create(
                model=FALLBACK_MODEL,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"}
            )
            return response.choices[0].message.content
        except Exception as fallback_err:
            st.error(f"فشل الاتصال بجميع النماذج: {fallback_err}")
            return None

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
    st.header("إعدادات القناص")
    platform = st.radio("المنصة:", ["Pocket Option (Binary)", "فوركس (Scalping)"])
    symbol = st.selectbox("اختر الزوج", ["USD/JPY", "EUR/USD", "GBP/USD", "AUD/USD"])
    yf_symbol = symbol.replace("/", "") + "=X"
    
    st.divider()
    payout = st.number_input("نسبة العائد (Payout %):", min_value=10, max_value=100, value=75)
    st.info("💡 القناص يدخل حتى لو كان العائد منخفضاً إذا كانت ضربة السيولة قوية (Reclaim).")

# ================= 3. جلب البيانات (3 أطر زمنية) =================
@st.cache_data(ttl=60)
def get_market_data(sym):
    # جلب 15 دقيقة (للاتجاه)، 5 دقائق (للمراقبة)، 1 دقيقة (للدخول القناص)
    df_15m = yf.download(sym, period="5d", interval="15m", auto_adjust=True, progress=False)
    df_5m = yf.download(sym, period="5d", interval="5m", auto_adjust=True, progress=False)
    df_1m = yf.download(sym, period="1d", interval="1m", auto_adjust=True, progress=False)
    
    if df_15m.empty or df_5m.empty or df_1m.empty: return None, None, None
    
    for df in [df_15m, df_5m, df_1m]:
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        df.columns = [c.lower() for c in df.columns]
        df['rsi'] = ta.rsi(df['close'], length=14)
        df['ema50'] = ta.ema(df['close'], length=50)
        # حساب ذيل الشمعة السفلي (لاصطياد الفخ)
        df['lower_wick'] = df[['open', 'close']].min(axis=1) - df['low']
        df['body'] = abs(df['open'] - df['close'])
        
    return df_15m, df_5m, df_1m

df_15m, df_5m, df_1m = get_market_data(yf_symbol)

if df_15m is None or df_1m is None:
    st.error("تعذر جلب البيانات.")
    st.stop()

current_price = float(df_1m.iloc[-1]['close'])
last_m1 = df_1m.iloc[-1]

# ================= 4. التبويبات =================
tab_chart, tab_sniper = st.tabs(["📈 الشارت (15m)", "🎯 قناص السيولة (Rebound)"])

with tab_chart:
    chart_df = df_15m.reset_index()
    time_col = 'Datetime' if 'Datetime' in chart_df.columns else 'Date'
    chart_df['time'] = pd.to_datetime(chart_df[time_col]).apply(lambda x: int(time.mktime(x.timetuple())))
    
    candles = [{"type": 'Candlestick', "data": chart_df[['time', 'open', 'high', 'low', 'close']].dropna().to_dict('records'), "options": {"upColor": '#26a69a', "downColor": '#ef5350'}}]
    ema = [{"type": 'Line', "data": chart_df[['time', 'ema50']].dropna().rename(columns={'ema50': 'value'}).to_dict('records'), "options": {"color": '#f59e0b', "lineWidth": 2}}]
    
    chartOptions = {"height": 500, "layout": {"textColor": '#d1d4dc', "background": {"type": 'solid', "color": '#0a0a0f'}}, "grid": {"vertLines": {"color": '#1e1e2d'}, "horzLines": {"color": '#1e1e2d'}}, "timeScale": {"timeVisible": True}, "handleScroll": True, "handleScale": True}
    renderLightweightCharts([{"chart": chartOptions, "series": candles + ema}], 'chart1')

with tab_sniper:
    st.subheader("🎯 Thunder Liquidity Sniper")
    st.write(f"السعر الحالي: **{current_price:.3f}** | العائد: **{payout}%**")
    
    if st.button("⚡ ابحث عن ضربة سيولة (Stop Hunt)", use_container_width=True):
        with st.spinner("جاري فحص شموع الدقيقة لاكتشاف الفخ والارتداد..."):
            try:
                # تجهيز بيانات دقيقة 1
                m1_data = df_1m.tail(3)[['open', 'high', 'low', 'close', 'lower_wick', 'body', 'rsi']].to_string()
                m15_data = df_15m.tail(2)[['close', 'ema50', 'rsi']].to_string()

                prompt = f"""
                أنت "Thunder Sniper Pro"، خبير في مفاهيم الأموال الذكية (Smart Money Concepts). 
                أنت تبحث عن مصيدة السيولة (Stop Hunt) والاقتناص (Reclaim).
                
                السعر الحالي: {current_price:.3f}
                بيانات إطار 15 دقيقة (للاتجاه): {m15_data}
                بيانات إطار 1 دقيقة (للدخول): {m1_data}
                
                القواعد الصارمة (يجب تطبيقها بدقة):
                1. الاتجاه: السعر يجب أن يكون فوق EMA50 على 15 دقيقة.
                2. مصيدة السيولة: يجب أن نرى شمعة دقيقة هبطت بقوة وكسرت قاعاً سابقاً، ولها ذيل سفلي طويل (lower_wick > body). هذا يعني أن صانع السوق ضرب وقف الخسائر.
                3. الاقتناص (Reclaim): يجب أن تكون الشمعة الأخيرة خضراء (close > open) وأغلقت فوق المستوى المكسور. هذا هو دخولنا.
                4. المدة: **5 دقائق فقط**. (لأن الحركة الانفجارية تحدث في أول دقائق).
                5. إذا لم تكن الشمعة الأخيرة خضراء قوية أو لم يوجد ذيل سفلي طويل، القرار يجب أن يكون "انتظار".
                
                أريد الإجابة بصيغة JSON فقط:
                {{
                    "trap_detected": true/false,
                    "reclaim_confirmed": true/false,
                    "scenarios": [
                        {{"type": "صعودي (ارتداد)", "probability": "نسبة", "reasoning": "السبب"}},
                        {{"type": "هبوطي (استمرار)", "probability": "نسبة", "reasoning": "السبب"}}
                    ],
                    "final_decision": {{
                        "direction": "شراء" أو "انتظار",
                        "entry_price": "{current_price:.3f}",
                        "tp": "هدف الربح",
                        "sl": "وقف الخسارة",
                        "trade_duration": "5 دقائق",
                        "confidence": "النسبة الحقيقية"
                    }},
                    "summary": "اشرح لي كيف حدثت ضربة السيولة، وكيف ارتد السعر، ولماذا هذه الصفقة آمنة."
                }}
                """
                
                response_text = generate_analysis(prompt)
                if not response_text:
                    st.stop()
                
                clean_json = response_text.strip()
                if clean_json.startswith("```json"):
                    clean_json = clean_json[7:-3].strip()
                elif clean_json.startswith("```"):
                    clean_json = clean_json[3:-3].strip()
                
                plan = json.loads(clean_json)
                final = plan.get('final_decision', {})
                
                if final.get('direction') == "انتظار":
                    st.warning("🛑 **القناص ينتظر:** لم يتم اكتشاف ضربة سيولة (Stop Hunt) واضحة، أو لم يتم تأكيد الاقتناص (Reclaim). لا تدخل الآن.")
                    st.info(f"**السبب:** {plan.get('summary')}")
                else:
                    st.success(f"🎯 **تم اصطياد السيولة!** القرار: {final.get('direction')} (ثقة: {final.get('confidence')})")
                    
                    st.markdown("### 🧠 تحليل صانع السوق (Smart Money)")
                    st.write(plan.get('summary'))
                    
                    st.divider()
                    
                    c1, c2, c3, c4 = st.columns(4)
                    c1.info(f"**نقطة الدخول**\n\n### {final.get('entry_price')}")
                    c2.success(f"**هدف الربح**\n\n### {final.get('tp')}")
                    c3.error(f"**وقف الخسارة**\n\n### {final.get('sl')}")
                    c4.warning(f"**زمن الصفقة**\n\n### {final.get('trade_duration')}")
                    
                    msg = f"⚡ *Thunder Sniper (Liquidity)* ⚡\nالزوج: {symbol}\nالقرار: {final.get('direction')} (ثقة {final.get('confidence')})\nالعائد: {payout}%\nالدخول: {final.get('entry_price')}\nالهدف: {final.get('tp')}\nالوقف: {final.get('sl')}\n*الوقت:* {final.get('trade_duration')}\n\n*السبب:* {plan.get('summary')}"
                    if send_telegram_alert(msg):
                        st.toast("📤 تم إرسال الصفقة إلى تليجرام!")
                        
            except Exception as e:
                st.error(f"حدث خطأ في التحليل: {e}")
