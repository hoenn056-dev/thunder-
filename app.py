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
st.title("⚡ Thunder - Sniper Scalping System")

# ================= 1. إعداد الذكاء الاصطناعي =================
try:
    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=st.secrets["OPENROUTER_API_KEY"],
    )
    PRIMARY_MODEL = "deepseek/deepseek-v4.1-flash-1017"
    FALLBACK_MODEL = "meta-llama/llama-3-8b-instruct:free"
except Exception as e:
    st.error(f"خطأ في مفتاح OpenRouter: {e}. تأكد من إضافته في Secrets.")

def generate_analysis(prompt):
    try:
        response = client.chat.completions.create(
            model=PRIMARY_MODEL,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.1 # درجة حرارة منخفضة جداً لضمان الدقة والمنطق
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

# ================= 2. جلب البيانات لعدة أزواج =================
PAIRS = ["USD/JPY", "EUR/USD", "GBP/USD", "AUD/USD", "USD/CAD"]

@st.cache_data(ttl=60)
def get_market_data(sym):
    yf_symbol = sym.replace("/", "") + "=X"
    df_main = yf.download(yf_symbol, period="5d", interval="15m", auto_adjust=True, progress=False)
    df_entry = yf.download(yf_symbol, period="5d", interval="5m", auto_adjust=True, progress=False)
    
    if df_main.empty or df_entry.empty: return None, None
    
    for df in [df_main, df_entry]:
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        df.columns = [c.lower() for c in df.columns]
        df['rsi'] = ta.rsi(df['close'], length=14)
        df['ema50'] = ta.ema(df['close'], length=50)
        df['atr'] = ta.atr(df['high'], df['low'], df['close'], length=14)
        
    return df_main, df_entry

# ================= 3. الإعدادات الجانبية =================
with st.sidebar:
    st.header("إعدادات السوق")
    platform = st.radio("اختر المنصة:", ["Pocket Option (Binary)", "تداول فوركس (Scalping)"])
    symbol_chart = st.selectbox("اعرض الشارت لزوج:", PAIRS)
    df_main, df_entry = get_market_data(symbol_chart)
    
    if df_main is None:
        st.error("تعذر جلب البيانات للشارت.")
        st.stop()
        
    current_price_chart = float(df_entry.iloc[-1]['close'])

# ================= 4. التبويبات =================
tab_chart, tab_trade = st.tabs(["📈 الشارت", "🎯 القناص (أفضل صفقة)"])

with tab_chart:
    chart_df = df_main.reset_index()
    time_col = 'Datetime' if 'Datetime' in chart_df.columns else 'Date'
    chart_df['time'] = pd.to_datetime(chart_df[time_col]).apply(lambda x: int(time.mktime(x.timetuple())))
    
    candles = [{"type": 'Candlestick', "data": chart_df[['time', 'open', 'high', 'low', 'close']].dropna().to_dict('records'), "options": {"upColor": '#26a69a', "downColor": '#ef5350'}}]
    ema = [{"type": 'Line', "data": chart_df[['time', 'ema50']].dropna().rename(columns={'ema50': 'value'}).to_dict('records'), "options": {"color": '#f59e0b', "lineWidth": 2}}]
    
    chartOptions = {"height": 500, "layout": {"textColor": '#d1d4dc', "background": {"type": 'solid', "color": '#0a0a0f'}}, "grid": {"vertLines": {"color": '#1e1e2d'}, "horzLines": {"color": '#1e1e2d'}}, "timeScale": {"timeVisible": True}, "handleScroll": True, "handleScale": True}
    renderLightweightCharts([{"chart": chartOptions, "series": candles + ema}], 'chart1')

with tab_trade:
    st.subheader("🎯 محرك القناصة (Sniper Engine)")
    st.write("سيقوم الذكاء الاصطناعي بفحص جميع الأزواج واختيار **الصفقة المثالية الوحيدة**. إذا لم يجد صفقة آمنة، سينصحك بالانتظار.")
    
    if st.button("⚡ ابحث عن أفضل صفقة الآن", use_container_width=True):
        with st.spinner("جاري فحص جميع الأزواج لاصطياد أفضل صفقة..."):
            try:
                # تجهيز بيانات جميع الأزواج
                all_pairs_data = ""
                for p in PAIRS:
                    df_m, df_e = get_market_data(p)
                    if df_m is not None and len(df_m) > 0:
                        price = float(df_e.iloc[-1]['close'])
                        data_15m = df_m.tail(2)[['close', 'rsi', 'ema50']].to_dict()
                        data_5m = df_e.tail(2)[['close', 'rsi', 'ema50']].to_dict()
                        all_pairs_data += f"\n--- {p} (السعر: {price:.3f}) ---\n15m: {data_15m}\n5m: {data_5m}\n"

                prompt = f"""
                أنت "قناص" تداول محترف (Sniper Trader). هدفك هو الحفاظ على رأس المال وعدم الدخول إلا في الصفقات المثالية (نسبة نجاح عالية جداً).
                لقد قمت بفحص الأزواج التالية. بيانات آخر شمعتين لكل زوج:
                {all_pairs_data}
                
                القواعد الصارمة جداً (يجب اتباعها):
                1. **أفضل زوج:** عليك مقارنة كل الأزواج واختيار الزوج الوحيد الذي يمتلك أقوى إشارة (Confluence) بين إطار 15 دقيقة و 5 دقائق.
                2. **الفلترة:** إذا لم يكن هناك توافق واضح، يجب أن يكون القرار "انتظار" (No Trade). لا تجبرني على الدخول.
                3. **زمن الصفقة:** اختر "5 دقائق" إذا كان السعر قريباً جداً من الدعم/المقاومة (سكالبينج سريع). اختر "15 دقيقة" إذا كان يحتاج مسافة أطول.
                4. **الثقة:** لا تعطني ثقة وهمية. اكتب النسبة الحقيقية بناءً على قوة الإشارة (فقط إذا كانت الإشارة قوية جداً، ستكون الثقة 85% أو أكثر).
                5. **الشرح:** اشرح لي بالتفصيل لماذا اخترت هذا الزوج بالذات، ولماذا هذه الصفقة "هي الأفضل".
                
                أريد الإجابة بصيغة JSON فقط:
                {{
                    "best_pair": "اسم الزوج الذي اخترته (أو لا يوجد)",
                    "why_best_pair": "لماذا هذا الزوج هو الأفضل الآن؟ (تفصيل)",
                    "scenarios": [
                        {{"type": "صعودي", "probability": "نسبة", "reasoning": "السبب"}},
                        {{"type": "هبوطي", "probability": "نسبة", "reasoning": "السبب"}}
                    ],
                    "final_decision": {{
                        "direction": "شراء" أو "بيع" أو "انتظار",
                        "entry_price": "سعر الدخول",
                        "tp": "هدف الربح",
                        "sl": "وقف الخسارة",
                        "trade_duration": "5 دقائق" أو "15 دقيقة",
                        "confidence": "النسبة الحقيقية (مثلاً 70% أو 85%)"
                    }},
                    "summary": "ملخص تنفيذي للصفقة"
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
                
                # عرض النتيجة
                if final.get('direction') == "انتظار":
                    st.warning("🛑 **القناص ينصح بالانتظار:** السوق الحالي لا يوفر صفقة آمنة بنسبة عالية. لا تخاطر بأموالك الآن.")
                    st.info(f"**السبب:** {plan.get('why_best_pair')}")
                else:
                    st.success(f"🎯 **الزوج الأفضل:** {plan.get('best_pair')} | **القرار:** {final.get('direction')} (ثقة: {final.get('confidence')})")
                    
                    st.markdown("### 🧠 لماذا هذه الصفقة هي الأفضل؟")
                    st.write(plan.get('why_best_pair'))
                    
                    st.markdown("### 🔮 تحليل السيناريوهات")
                    for scenario in plan.get('scenarios', []):
                        with st.expander(f"سيناريو {scenario.get('type')} (الاحتمالية: {scenario.get('probability')})"):
                            st.write(scenario.get('reasoning'))
                    
                    st.divider()
                    
                    c1, c2, c3, c4 = st.columns(4)
                    c1.info(f"**نقطة الدخول**\n\n### {final.get('entry_price')}")
                    c2.success(f"**هدف الربح**\n\n### {final.get('tp')}")
                    c3.error(f"**وقف الخسارة**\n\n### {final.get('sl')}")
                    c4.warning(f"**زمن الصفقة**\n\n### {final.get('trade_duration')}")
                    
                    st.info(f"**الملخص:** {plan.get('summary')}")
                    
                    msg = f"⚡ *Thunder Sniper* ⚡\nالزوج: {plan.get('best_pair')}\nالقرار: {final.get('direction')} (ثقة {final.get('confidence')})\nالدخول: {final.get('entry_price')}\nالهدف: {final.get('tp')}\nالوقف: {final.get('sl')}\n*الوقت:* {final.get('trade_duration')}\n\n*السبب:* {plan.get('why_best_pair')}"
                    if send_telegram_alert(msg):
                        st.toast("📤 تم إرسال الصفقة إلى تليجرام!")
                        
            except Exception as e:
                st.error(f"حدث خطأ في التحليل: {e}")
