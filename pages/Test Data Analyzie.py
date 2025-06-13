import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="📊 ความคิดเห็นแบบยืดหยุ่น", layout="wide")
st.title("📈 วิเคราะห์ข้อมูลแบบกลุ่ม + ประเภท (Grouped Bar Chart)")

uploaded_file = st.file_uploader("📁 อัปโหลดไฟล์ .csv หรือ .xlsx", type=["csv", "xlsx"])

if uploaded_file:
    # โหลดไฟล์
    if uploaded_file.name.endswith(".csv"):
        df = pd.read_csv(uploaded_file)
    else:
        df = pd.read_excel(uploaded_file)

    st.subheader("🧾 ตัวอย่างข้อมูลจากไฟล์")
    st.dataframe(df)

    # เฉพาะคอลัมน์ข้อความ (ใช้สำหรับ Group และ Category)
    text_cols = df.select_dtypes(include="object").columns.tolist()

    if len(text_cols) < 2:
        st.error("❌ ต้องมีคอลัมน์ข้อความอย่างน้อย 2 คอลัมน์")
    else:
        group_col = st.selectbox("📋 เลือกคอลัมน์หลักเพื่อจัดกลุ่ม (เช่น สาขา)", text_cols)
        category_col = st.selectbox(
            "🏷️ เลือกคอลัมน์ประเภทข้อมูล (เช่น ประเภทความคิดเห็น)", text_cols, index=1
        )

        if group_col and category_col:
            # เตรียมข้อมูล
            grouped_df = (
                df[[group_col, category_col]]
                .dropna()
                .groupby([group_col, category_col])
                .size()
                .reset_index(name="จำนวน")
            )

            # กราฟ
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
