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
st.title("⚡ Thunder Sniper Pro (Rebound Theory)")

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
    st.header("إعدادات السوق")
    platform = st.radio("اختر المنصة:", ["Pocket Option (Binary)", "تداول فوركس (Scalping)"])
    symbol = st.selectbox("اختر الزوج", ["USD/JPY", "EUR/USD", "GBP/USD", "AUD/USD"])
    yf_symbol = symbol.replace("/", "") + "=X"
    
    st.divider()
    # إضافة نسبة العائد (Payout) كما طلبت
    payout = st.number_input("نسبة العائد الحالية (Payout %):", min_value=10, max_value=100, value=75, step=1)
    st.info("💡 لا يتم الدخول إذا كان العائد أقل من 70%.")

# ================= 3. جلب البيانات =================
@st.cache_data(ttl=60)
def get_market_data(sym):
    # نجلب 15 دقيقة للاتجاه، و 5 دقائق للدخول
    df_15m = yf.download(sym, period="5d", interval="15m", auto_adjust=True, progress=False)
    df_5m = yf.download(sym, period="5d", interval="5m", auto_adjust=True, progress=False)
    
    if df_15m.empty or df_5m.empty: return None, None
    
    for df in [df_15m, df_5m]:
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        df.columns = [c.lower() for c in df.columns]
        df['rsi'] = ta.rsi(df['close'], length=14)
        df['ema50'] = ta.ema(df['close'], length=50)
        # حساب طول ذيل الشمعة (لاصطياد ضربات السيولة)
        df['lower_wick'] = df[['open', 'close']].min(axis=1) - df['low']
        df['body'] = abs(df['open'] - df['close'])
        
    return df_15m, df_5m

df_15m, df_5m = get_market_data(yf_symbol)

if df_15m is None or df_5m is None:
    st.error("تعذر جلب البيانات.")
    st.stop()

current_price = float(df_5m.iloc[-1]['close'])

# ================= 4. التبويبات =================
tab_chart, tab_sniper = st.tabs(["📈 الشارت", "🎯 القناص (Rebound)"])

with tab_chart:
    chart_df = df_15m.reset_index()
    time_col = 'Datetime' if 'Datetime' in chart_df.columns else 'Date'
    chart_df['time'] = pd.to_datetime(chart_df[time_col]).apply(lambda x: int(time.mktime(x.timetuple())))
    
    candles = [{"type": 'Candlestick', "data": chart_df[['time', 'open', 'high', 'low', 'close']].dropna().to_dict('records'), "options": {"upColor": '#26a69a', "downColor": '#ef5350'}}]
    ema = [{"type": 'Line', "data": chart_df[['time', 'ema50']].dropna().rename(columns={'ema50': 'value'}).to_dict('records'), "options": {"color": '#f59e0b', "lineWidth": 2}}]
    
    chartOptions = {"height": 500, "layout": {"textColor": '#d1d4dc', "background": {"type": 'solid', "color": '#0a0a0f'}}, "grid": {"vertLines": {"color": '#1e1e2d'}, "horzLines": {"color": '#1e1e2d'}}, "timeScale": {"timeVisible": True}, "handleScroll": True, "handleScale": True}
    renderLightweightCharts([{"chart": chartOptions, "series": candles + ema}], 'chart1')

with tab_sniper:
    st.subheader("🎯 Thunder Sniper Pro (نظرية الارتداد)")
    st.write("النظام يبحث عن فخ السيولة (Liquidity Grab) والارتداد الحقيقي. لن يدخل إلا إذا كان العائد 70%+.")
    
    if st.button("⚡ فحص السوق واصطياد الارتداد", use_container_width=True):
        if payout < 70:
            st.error(f"🛑 العائد الحالي ({payout}%) أقل من 70%. القناص يرفض الدخول في هذه الظروف.")
            st.stop()
            
        with st.spinner("جاري فحص الشموع لاكتشاف ضربات السيولة..."):
            try:
                # تجهيز بيانات آخر 3 شموع على 15m و 5m
                data_15m = df_15m.tail(3)[['open', 'high', 'low', 'close', 'rsi', 'ema50']].to_string()
                data_5m = df_5m.tail(3)[['open', 'high', 'low', 'close', 'rsi', 'lower_wick', 'body']].to_string()

                prompt = f"""
                أنت "Thunder Sniper Pro"، متداول مؤسسي خبير في استراتيجية (Liquidity Grab & Rebound) على منصة Pocket Option.
                السعر الحالي: {current_price:.3f}
                نسبة العائد (Payout): {payout}%
                
                بيانات إطار 15 دقيقة (للاتجاه العام):
                {data_15m}
                
                بيانات إطار 5 دقائق (للدخول واصطياد السيولة):
                {data_5m}
                
                الاستراتيجية الصارمة (يجب اتباعها حرفياً):
                1. **الاتجاه:** يجب أن يكون السعر فوق EMA50 على إطار 15 دقيقة.
                2. **الفخ (Trap):** راقب شموع 5 دقائق. هل هناك شمعة لها ذيل سفلي طويل (Lower Wick > Body)؟ هذا يعني أن صانع السوق ضرب وقف الخسائر وجمع السيولة.
                3. **الارتداد (Rebound):** بعد الذيل السفلي، هل أغلقت الشمعة الحالية خضراء وقوية؟ هذا هو دخولنا.
                4. **لا تشترِ في القمة أبداً:** إذا كان السعر مرتفعاً جداً و RSI متشبعاً (أعلى من 70)، يجب أن يكون القرار "انتظار".
                5. **المدة:** 15 دقيقة فقط (لإعطاء السعر وقتاً للارتداد).
                
                أريد الإجابة بصيغة JSON فقط:
                {{
                    "trap_detected": true/false,
                    "rebound_confirmed": true/false,
                    "scenarios": [
                        {{"type": "صعودي (ارتداد)", "probability": "نسبة", "reasoning": "السبب"}},
                        {{"type": "هبوطي (استمرار)", "probability": "نسبة", "reasoning": "السبب"}}
                    ],
                    "final_decision": {{
                        "direction": "شراء" أو "انتظار",
                        "entry_price": "{current_price:.3f}",
                        "tp": "هدف الربح",
                        "sl": "وقف الخسارة",
                        "trade_duration": "15 دقيقة",
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
                
                # عرض النتائج
                if final.get('direction') == "انتظار":
                    st.warning("🛑 **لا توجد ضربة سيولة واضحة:** السوق الحالي لا يوفر فخاً حقيقياً. انتظر ولا تخاطر.")
                    st.info(f"**السبب:** {plan.get('summary')}")
                else:
                    st.success(f"🎯 **تم اصطياد الارتداد!** القرار: {final.get('direction')} (ثقة: {final.get('confidence')})")
                    
                    st.markdown("### 🧠 تحليل صانع السوق (Smart Money)")
                    st.write(plan.get('summary'))
                    
                    st.divider()
                    
                    c1, c2, c3, c4 = st.columns(4)
                    c1.info(f"**نقطة الدخول**\n\n### {final.get('entry_price')}")
                    c2.success(f"**هدف الربح**\n\n### {final.get('tp')}")
                    c3.error(f"**وقف الخسارة**\n\n### {final.get('sl')}")
                    c4.warning(f"**زمن الصفقة**\n\n### {final.get('trade_duration')}")
                    
                    msg = f"⚡ *Thunder Sniper Pro* ⚡\nالزوج: {symbol}\nالقرار: {final.get('direction')} (ثقة {final.get('confidence')})\nالعائد: {payout}%\nالدخول: {final.get('entry_price')}\nالهدف: {final.get('tp')}\nالوقف: {final.get('sl')}\n*الوقت:* {final.get('trade_duration')}\n\n*السبب:* {plan.get('summary')}"
                    if send_telegram_alert(msg):
                        st.toast("📤 تم إرسال الصفقة إلى تليجرام!")
                        
            except Exception as e:
                st.error(f"حدث خطأ في التحليل: {e}")
