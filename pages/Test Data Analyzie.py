import streamlit as st
import pandas as pd
import plotly.express as px
from openai import OpenAI
from config import OPENAI_API_KEY, CHAT_TOKEN
import plotly.io as pio
from io import BytesIO


# เชื่อมต่อ API (ใส่ key จริงของคุณใน OPENAI_API_KEY)
client = OpenAI(api_key=OPENAI_API_KEY)

st.set_page_config(page_title="📊 ความคิดเห็นแบบยืดหยุ่น", layout="wide")
st.title("📈 วิเคราะห์ข้อมูลแบบกลุ่ม + ประเภท (Grouped Bar Chart)")

uploaded_file = st.file_uploader("📁 อัปโหลดไฟล์ .csv หรือ .xlsx", type=["csv", "xlsx"])

if uploaded_file:
    if uploaded_file.name.endswith(".csv"):
        df = pd.read_csv(uploaded_file)
    else:
        df = pd.read_excel(uploaded_file)

    st.subheader("🧾 ตัวอย่างข้อมูลจากไฟล์")
    st.dataframe(df)

    text_cols = df.select_dtypes(include="object").columns.tolist()

    if len(text_cols) < 2:
        st.error("❌ ต้องมีคอลัมน์ข้อความอย่างน้อย 2 คอลัมน์")
    else:
        group_col = st.selectbox("📋 เลือกคอลัมน์หลักเพื่อจัดกลุ่ม (เช่น สาขา)", text_cols)
        category_col = st.selectbox(
            "🏷️ เลือกคอลัมน์ประเภทข้อมูล (เช่น ประเภทความคิดเห็น)", text_cols, index=1
        )

        if group_col and category_col:
            grouped_df = (
                df[[group_col, category_col]]
                .dropna()
                .groupby([group_col, category_col])
                .size()
                .reset_index(name="จำนวน")
            )

            fig = px.bar(
                grouped_df,
                x=group_col,
                y="จำนวน",
                color=category_col,
                barmode="group",
                text="จำนวน",
                title=f"จำนวน '{category_col}' ในแต่ละ '{group_col}'",
                height=500,
            )

            fig.update_layout(xaxis_title=group_col, yaxis_title="จำนวน")
            st.subheader("📊 กราฟเปรียบเทียบแบบกลุ่ม")
            st.plotly_chart(fig, use_container_width=True)

            # 🔽 แปลงกราฟเป็นภาพ PNG
            img_bytes = BytesIO()
            pio.write_image(fig, img_bytes, format="png", width=1000, height=600, scale=2)
            img_bytes.seek(0)
            # 🔘 ปุ่มดาวน์โหลด
            st.download_button(
                label="💾 ดาวน์โหลดกราฟเป็น PNG",
                data=img_bytes,
                file_name="grouped_bar_chart.png",
                mime="image/png"
            )
            
            # ✅ วิเคราะห์ด้วย AI
            if st.button("🔍 วิเคราะห์ข้อมูลด้วย AI"):
                with st.spinner("🤖 AI กำลังวิเคราะห์ข้อมูล..."):

                    prompt = f"""ต่อไปนี้คือข้อมูลจำนวน {category_col} ในแต่ละ {group_col}:
{grouped_df.to_string(index=False)}

กรุณาวิเคราะห์ข้อมูลนี้โดยสรุป:
- กลุ่มไหนโดดเด่นหรือต่ำกว่ากลุ่มอื่น
- ประเภทใดถูกกล่าวถึงมากที่สุดในภาพรวม
- แนวโน้มที่น่าสนใจ
- ข้อเสนอแนะเชิงกลยุทธ์"""

                    response = client.chat.completions.create(
                        model="gpt-4", messages=[{"role": "user", "content": prompt}]
                    )
                    ai_result = response.choices[0].message.content
                    st.markdown("### 🤖 วิเคราะห์โดย AI")
                    st.success(ai_result)
                    

