import streamlit as st
import pandas as pd
import plotly.express as px
from io import BytesIO
import plotly.io as pio
from openai import OpenAI
from config import OPENAI_API_KEY

client = OpenAI(api_key=OPENAI_API_KEY)
st.set_page_config(page_title="📊 วิเคราะห์ความคิดเห็น", layout="wide")
st.title("📈 วิเคราะห์ข้อมูลแบบกลุ่ม + ประเภท (Grouped Chart)")


# ✅ ฟังก์ชัน: สร้างกราฟกลุ่ม
def plot_grouped_chart(df, group_col, category_col, chart_type="bar"):
    grouped_df = (
        df[[group_col, category_col]]
        .dropna()
        .groupby([group_col, category_col])
        .size()
        .reset_index(name="จำนวน")
    )

    if chart_type == "bar":
        fig = px.bar(
            grouped_df,
            x=group_col,
            y="จำนวน",
            color=category_col,
            barmode="group",
            text="จำนวน",
            title=f"จำนวน '{category_col}' ในแต่ละ '{group_col}'",
        )
    elif chart_type == "line":
        fig = px.line(
            grouped_df,
            x=group_col,
            y="จำนวน",
            color=category_col,
            markers=True,
            title=f"แนวโน้ม '{category_col}' ในแต่ละ '{group_col}'",
        )
    elif chart_type == "area":
        fig = px.area(
            grouped_df,
            x=group_col,
            y="จำนวน",
            color=category_col,
            title=f"พื้นที่สะสมของ '{category_col}' ในแต่ละ '{group_col}'",
        )
    elif chart_type == "pie":
        fig = px.pie(
            grouped_df,
            names=category_col,
            values="จำนวน",
            title=f"สัดส่วน '{category_col}' รวมจากทุก '{group_col}'",
        )
    elif chart_type == "heatmap":
        heat_df = grouped_df.pivot(
            index=group_col, columns=category_col, values="จำนวน"
        ).fillna(0)
        fig = px.imshow(
            heat_df,
            labels=dict(x=category_col, y=group_col, color="จำนวน"),
            title=f"Heatmap: ความหนาแน่นของ '{category_col}' ในแต่ละ '{group_col}'",
        )
    elif chart_type == "treemap":
        fig = px.treemap(
            grouped_df,
            path=[group_col, category_col],
            values="จำนวน",
            title=f"Treemap ของ '{group_col}' และ '{category_col}' ตามจำนวน",
        )
    else:
        st.error("❌ ประเภทกราฟไม่รองรับ")
        return grouped_df

    fig.update_layout(height=500)

    st.subheader("📊 กราฟแสดงผล")
    st.plotly_chart(fig, use_container_width=True)

    # 🔘 ปุ่มดาวน์โหลดกราฟ (ยกเว้น heatmap/treemap อาจไม่ render บางเครื่อง)
    if chart_type not in ["pie", "heatmap", "treemap"]:
        img_bytes = BytesIO()
        pio.write_image(fig, img_bytes, format="png", width=1000, height=600, scale=2)
        img_bytes.seek(0)
        st.download_button(
            label="💾 ดาวน์โหลดกราฟเป็น PNG",
            data=img_bytes,
            file_name="grouped_chart.png",
            mime="image/png",
        )

    return grouped_df


# ✅ ฟังก์ชัน: วิเคราะห์ด้วย GPT
def analyze_with_gpt(grouped_df, group_col, category_col):
    prompt = f"""ต่อไปนี้คือข้อมูลจำนวน {category_col} ในแต่ละ {group_col}:
{grouped_df.to_string(index=False)}

กรุณาวิเคราะห์ข้อมูลนี้โดยสรุป:
- กลุ่มไหนโดดเด่นหรือต่ำกว่ากลุ่มอื่น
- ประเภทใดถูกกล่าวถึงมากที่สุดในภาพรวม
- แนวโน้มที่น่าสนใจ
- ข้อเสนอแนะเชิงกลยุทธ์"""

    with st.spinner("🤖 AI กำลังวิเคราะห์ข้อมูล..."):
        response = client.chat.completions.create(
            model="gpt-4", messages=[{"role": "user", "content": prompt}]
        )
        ai_result = response.choices[0].message.content.strip()

    st.markdown("### 🤖 วิเคราะห์โดย AI")
    st.markdown(ai_result)


# ===== อัปโหลดหลายไฟล์ =====
uploaded_files = st.file_uploader(
    "📂 อัปโหลดไฟล์ (.csv หรือ .xlsx)", type=["csv", "xlsx"], accept_multiple_files=True
)

if uploaded_files:
    all_dfs = []
    for uploaded_file in uploaded_files:
        try:
            if uploaded_file.name.endswith(".csv"):
                df = pd.read_csv(uploaded_file)
            else:
                df = pd.read_excel(uploaded_file)
            df["📁_แหล่งไฟล์"] = uploaded_file.name
            all_dfs.append(df)
        except Exception as e:
            st.error(f"❌ อ่านไฟล์ {uploaded_file.name} ไม่สำเร็จ: {e}")

    if all_dfs:
        df = pd.concat(all_dfs, ignore_index=True)
        st.subheader("🧾 ข้อมูลรวมจากทุกไฟล์")
        st.dataframe(df)

        text_cols = df.select_dtypes(include="object").columns.tolist()
        if len(text_cols) < 2:
            st.error("❌ ต้องมีคอลัมน์ข้อความอย่างน้อย 2 คอลัมน์เพื่อวิเคราะห์")
        else:
            group_col = st.selectbox("📋 คอลัมน์สำหรับจัดกลุ่ม (Group)", text_cols)
            category_col = st.selectbox("🏷️ คอลัมน์สำหรับแยกประเภท", text_cols, index=1)
            chart_type = st.selectbox(
                "📊 เลือกรูปแบบกราฟที่ต้องการ",
                ["bar", "line", "area", "pie", "heatmap", "treemap"],
                index=0,
                format_func=lambda x: {
                    "bar": "แท่ง (Bar)",
                    "line": "เส้น (Line)",
                    "area": "พื้นที่ (Area)",
                    "pie": "วงกลม (Pie)",
                    "heatmap": "ฮีทแมพ (Heatmap)",
                    "treemap": "ทรีแมพ (Treemap)",
                }[x],
            )

            if group_col and category_col:
                grouped_df = plot_grouped_chart(df, group_col, category_col, chart_type)

                if st.button("🔍 วิเคราะห์ข้อมูลด้วย AI") and grouped_df is not None:
                    analyze_with_gpt(grouped_df, group_col, category_col)
