# pages/Database.py
import os
import sqlite3
import pandas as pd
import streamlit as st
import tiktoken
from utility_chat import *

DB_PATH = "data/sqdata.db"

# ----------------------------
# ⚙️ Debug Mode Configuration
# ----------------------------
DEBUG = os.getenv("DEBUG", "0") == "1"

if DEBUG:
    # ตั้งค่า session ผู้ใช้ mock สำหรับการทดสอบ
    if "user_id" not in st.session_state:
        st.session_state["user_id"] = "Udebug123456"
        st.session_state["displayName"] = "U TEST"
        st.session_state["pictureUrl"] = "https://i.imgur.com/1Q9Z1Zm.png"
        st.session_state["status"] = "APPROVED"
        st.session_state["role"] = "super admin"
        st.info("🔧 Loaded mock user session for debugging.")

# 🔒 ตรวจสอบสิทธิ์เฉพาะ super admin เท่านั้น
if "role" not in st.session_state or st.session_state["role"] != "super admin":
    st.error("⛔ คุณไม่มีสิทธิ์เข้าถึงหน้านี้ (เฉพาะ super admin เท่านั้น)")
    st.stop()


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

        # ✅ จัดการ token count สำหรับตารางข้อความ
        if table_name == "messages" and "content" in df.columns:
            df["token_count"] = df["content"].apply(lambda x: count_tokens(x))

        # ✅ จัดรูปแบบ datetime
        if "created_at" in df.columns:
            df["created_at"] = pd.to_datetime(
                df["created_at"], errors="coerce"
            ).dt.strftime("%Y-%m-%d %H:%M:%S")

        # ✅ ขยับ token_count ไปท้ายตาราง
        if "token_count" in df.columns:
            cols = [col for col in df.columns if col != "token_count"] + ["token_count"]
            df = df[cols]

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
    "ส่งออกแล้ว (sent_records)": "sent_records",
    "JSON ต้นฉบับ (raw_jsons)": "raw_json",
}

# Left Pane Menu
menu = st.sidebar.radio("เมนู", ["📊 ข้อมูลจากฐานข้อมูล", "Backup/Restore db"])

if menu == "📊 ข้อมูลจากฐานข้อมูล":
    st.title("📊 ข้อมูลจากฐานข้อมูล")

    selected_label = st.selectbox("เลือกตาราง", list(TABLES.keys()))
    table_name = TABLES[selected_label]

    # ✅ reset page เมื่อเปลี่ยนตาราง
    if "last_table" not in st.session_state or st.session_state["last_table"] != table_name:
        st.session_state["page"] = 1
        st.session_state["last_table"] = table_name

    df = fetch_table(table_name)

    if df.empty:
        st.warning("⚠️ ไม่พบข้อมูลในตาราง หรือเกิดข้อผิดพลาดระหว่างอ่านข้อมูล")
    else:
        ROWS_PER_PAGE = 20
        total_rows = len(df)
        total_pages = (total_rows - 1) // ROWS_PER_PAGE + 1

        st.markdown(f"### 🧾 ตาราง: `{table_name}`")

        datacol1, datacol2, datacol3 = st.columns([4, 4, 2])
        with datacol1:
            st.markdown("")
        with datacol2:
            st.markdown("")
        with datacol3:
            st.session_state["page"] = st.number_input(
                "เลือกหน้าที่ต้องการ",
                min_value=1,
                max_value=total_pages,
                value=st.session_state.get("page", 1),
                step=1,
                key="page_input",
            )

        start_idx = (st.session_state["page"] - 1) * ROWS_PER_PAGE
        end_idx = start_idx + ROWS_PER_PAGE
        paginated_df = df.iloc[start_idx:end_idx]

        st.caption(
            f"🔢 แสดงหน้า {st.session_state['page']} จาก {total_pages} | รวมทั้งหมด {total_rows} แถว"
        )
        st.dataframe(paginated_df, use_container_width=True)

        st.download_button(
            "⬇️ ดาวน์โหลด CSV",
            df.to_csv(index=False).encode("utf-8-sig"),
            file_name=f"{table_name}.csv",
            mime="text/csv",
        )

elif menu == "Backup/Restore db":
    st.title("📦 Backup / Restore Database")
    st.markdown("""
        ### ℹ️ คำแนะนำสำหรับการใช้งานระบบ Backup / Restore ฐานข้อมูล

        - 🔒 **สำรองข้อมูลก่อนทุกการเปลี่ยนแปลงสำคัญ** เช่น อัปเดตโค้ด, เปลี่ยน schema, หรือเริ่มใช้งานจริง
        - 📥 **การกดปุ่ม "ดาวน์โหลด" จะบันทึกฐานข้อมูลเวอร์ชันปัจจุบัน** ลงเครื่องของคุณในรูปแบบไฟล์ `.db`
        - 📤 **การอัปโหลดไฟล์ Restore จะเขียนทับไฟล์ `sqdata.db` เดิมทันที**  
            ‣ โปรดตรวจสอบว่าไฟล์ที่ใช้คืนข้อมูลเป็นเวอร์ชันล่าสุด และได้จากแหล่งที่เชื่อถือได้  
            ‣ การ Restore ควรใช้เฉพาะในกรณีต้องย้อนกลับ หรือย้ายข้อมูล
        - ⚠️ **เมื่อ Restore สำเร็จ กรุณา refresh หน้าแอป (Ctrl+R หรือ F5)** เพื่อโหลดฐานข้อมูลใหม่เข้า memory
        - 📂 หากต้องการบริหารไฟล์สำรองอย่างเป็นระบบ ควรเก็บในโฟลเดอร์ `backup/` พร้อม timestamp ที่ชัดเจน

        > 💡 เพื่อความปลอดภัยระดับ production: ควรตั้งสิทธิ์การใช้งานฟังก์ชันนี้เฉพาะ admin หรือ super admin เท่านั้น
        """)
    # แบ่งเป็น 2 คอลัมน์
    backup1, backup2 = st.columns([1, 1])

    # 📥 คอลัมน์ซ้าย: Backup
    with backup1:
        st.subheader("📥 Backup Database")
        if os.path.exists(DB_PATH):
            with open(DB_PATH, "rb") as f:
                st.download_button(
                    label="⬇️ ดาวน์โหลด sqdata.db",
                    data=f,
                    file_name="sqdata.db",
                    mime="application/octet-stream"
                )
        else:
            st.error("❌ ไม่พบไฟล์ฐานข้อมูล: data/sqdata.db")

    # 📤 คอลัมน์ขวา: Restore
    with backup2:
        st.subheader("📤 Restore Database")
        uploaded_file = st.file_uploader("อัปโหลดไฟล์ .db", type=["db"])

        if uploaded_file is not None:
            confirm = st.checkbox("⚠️ ยืนยันเขียนทับฐานข้อมูล", value=False, key="confirm_restore")
            if st.button("♻️ Restore ทับฐานข้อมูล", disabled=not confirm):
                try:
                    with open(DB_PATH, "wb") as f:
                        f.write(uploaded_file.read())
                    st.success("✅ กู้คืนฐานข้อมูลเรียบร้อยแล้ว!")
                    st.info("🔄 กรุณา refresh หน้าแอปเพื่อโหลดข้อมูลใหม่")
                except Exception as e:
                    st.error(f"❌ เกิดข้อผิดพลาดขณะเขียนไฟล์: {e}")