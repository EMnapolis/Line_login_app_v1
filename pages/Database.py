#pages/Database.py
import pandas as pd
import sqlite3
import streamlit as st
import os
import tiktoken

DB_PATH = "data/sqdata.db"

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
        df = pd.read_sql_query(f"SELECT * FROM {table_name} LIMIT 100", conn)
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
    st.caption(f"🔢 แสดงสูงสุด 100 แถว | รวมทั้งหมด {len(df)} แถว")
    st.dataframe(df)

    st.download_button(
        "⬇️ ดาวน์โหลด CSV",
        df.to_csv(index=False).encode("utf-8-sig"),
        file_name=f"{table_name}.csv",
        mime="text/csv"
    )
