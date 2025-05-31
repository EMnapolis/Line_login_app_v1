#Database
import pandas as pd
import sqlite3
import streamlit as st
import os
import tiktoken

DB_PATH = "data/sqdata.db"

# 🔒 ตรวจสอบสิทธิ์เฉพาะ super admin เท่านั้น
if "role" not in st.session_state or st.session_state["role"] != "super admin":
    st.error("⛔ คุณไม่มีสิทธิ์เข้าถึงหน้านี้ (เฉพาะ super admin เท่านั้น)")
    st.stop()  # 🛑 หยุดการทำงานหน้านี้ทั้งหมด

def count_tokens(text, model="gpt-3.5-turbo"):
    try:
        enc = tiktoken.encoding_for_model(model)
    except:
        enc = tiktoken.get_encoding("cl100k_base")  # fallback
    return len(enc.encode(text or ""))

def fetch_table(table_name):
    if not os.path.exists(DB_PATH):
        st.error(f"❌ ไม่พบไฟล์ฐานข้อมูล: {DB_PATH}")
        return pd.DataFrame()
    try:
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql_query(f"SELECT * FROM {table_name}", conn)
        conn.close()

        # ✅ เพิ่มคอลัมน์นับ token ถ้าเป็นตาราง messages
        if table_name == "messages" and "content" in df.columns:
            df["token_count"] = df["content"].apply(lambda x: count_tokens(x))

        return df
    except sqlite3.OperationalError as e:
        st.error(f"❌ SQLite Error: {e}")
        return pd.DataFrame()

# Mapping label to table names (whitelist)
TABLES = {
    "ผู้ใช้งาน (access_login)": "access_login",
    "บทสนทนา (conversations)": "conversations",
    "ข้อความ (messages)": "messages",
    "Prompts": "prompts",
    "ส่งออกแล้ว (sent_records)": "sent_records"
}

st.title("📊 ข้อมูลจากฐานข้อมูล")

selected_label = st.selectbox("เลือกตาราง", list(TABLES.keys()))
table_name = TABLES[selected_label]
df = fetch_table(table_name)

if df.empty:
    st.warning("⚠️ ไม่พบข้อมูลในตาราง หรือเกิดข้อผิดพลาดระหว่างอ่านข้อมูล")
else:
    # st.caption(f"🔢 แสดงสูงสุด 100 แถว | รวมทั้งหมด {len(df)} แถว")
    # st.dataframe(df)
    ROWS_PER_PAGE = 20  # จำนวนแถวต่อหน้า
    total_rows = len(df)
    total_pages = (total_rows - 1) // ROWS_PER_PAGE + 1

    page = st.number_input(
        "เลือกหน้าที่ต้องการ",
        min_value=1,
        max_value=total_pages,
        value=1,
        step=1
    )

    start_idx = (page - 1) * ROWS_PER_PAGE
    end_idx = start_idx + ROWS_PER_PAGE
    paginated_df = df.iloc[start_idx:end_idx]

    st.caption(f"🔢 แสดงหน้า {page} จาก {total_pages} | รวมทั้งหมด {total_rows} แถว")
    st.dataframe(paginated_df, use_container_width=True)

    st.download_button(
        "⬇️ ดาวน์โหลด CSV",
        df.to_csv(index=False).encode("utf-8-sig"),
        file_name=f"{table_name}.csv",
        mime="text/csv"
    )
