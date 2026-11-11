@st.cache_data(ttl=300)
def get_analysis(sym, tf):
    # تحديد الفترة المناسبة لكل إطار زمني لتجنب خطأ ياهو فاينانس
    if tf == "15m":
        period = "5d"   # الحد الأقصى لياهو هو 60 يوماً، 5 أيام آمنة جداً
    elif tf == "1h":
        period = "1mo"  # شهر كامل لبيانات الساعة
    else:
        period = "3mo"  # 3 أشهر للإطار اليومي

    df = yf.download(sym, period=period, interval=tf, auto_adjust=True)
    
    # إذا كانت البيانات فارغة (السوق مغلق أو خطأ في الشبكة)
    if df.empty:
        return None
    
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df.reset_index(inplace=True)
    
    time_col = 'Datetime' if 'Datetime' in df.columns else 'Date'
    df['time'] = pd.to_datetime(df[time_col]).apply(lambda x: int(time.mktime(x.timetuple())))
    df.columns = [c.lower() for c in df.columns]
    
    # حساب المؤشرات
    df['rsi'] = ta.rsi(df['close'], length=14)
    macd = ta.macd(df['close'])
    df['macd'] = macd['MACD_12_26_9']
    df['atr'] = ta.atr(df['high'], df['low'], df['close'], length=14)
    df['ema50'] = ta.ema(df['close'], length=50)
    
    last = df.iloc[-1]
    pivot = (last['high'] + last['low'] + last['close']) / 3
    r1 = (2 * pivot) - last['low']
    s1 = (2 * pivot) - last['high']
    
    current_price = last['close']
    atr = last['atr']
    if current_price > pivot:
        entry = current_price
        tp = entry + (atr * 2)
        sl = entry - (atr * 1.5)
        direction = "شراء (Long)"
    else:
        entry = current_price
        tp = entry - (atr * 2)
        sl = entry + (atr * 1.5)
        direction = "بيع (Short)"
        
    return df, current_price, last['rsi'], last['macd'], pivot, r1, s1, direction, entry, tp, sl
