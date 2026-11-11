with tab_chat:
    st.subheader("المحلل المؤسسي (مع دعم الصور)")
    
    # تهيئة سجل المحادثة (لن يُمسح أبداً)
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # عرض الرسائل السابقة
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if "image" in message:
                st.image(message["image"])

    # أداة رفع الصور
    uploaded_file = st.file_uploader("ارفع صورة شارت لتحليلها:", type=["png", "jpg", "jpeg"])

    if prompt := st.chat_input("اسأل Thunder..."):
        user_msg = {"role": "user", "content": prompt}
        if uploaded_file:
            user_msg["image"] = uploaded_file
        st.session_state.messages.append(user_msg)
        
        with st.chat_message("user"):
            st.markdown(prompt)
            if uploaded_file:
                st.image(uploaded_file)

        with st.chat_message("assistant"):
            with st.spinner("جاري التحليل العميق..."):
                try:
                    # تجهيز السياق الكامل (السعر + المؤشرات + الصورة)
                    context = f"السعر: {current_price:.3f}, RSI: {last_candle['rsi']:.1f}, الاتجاه: {direction}"
                    
                    if uploaded_file:
                        img = Image.open(uploaded_file)
                        response = model.generate_content([
                            f"أنت متداول مؤسسي. حلل هذه الصورة (شارت) باللغة العربية. السياق: {context}. سؤال: {prompt}",
                            img
                        ])
                    else:
                        response = model.generate_content(f"أنت متداول مؤسسي. السياق: {context}. أجب بالعربية: {prompt}")
                    
                    st.markdown(response.text)
                    st.session_state.messages.append({"role": "assistant", "content": response.text})
                except Exception as e:
                    st.error(f"خطأ: {e}")
