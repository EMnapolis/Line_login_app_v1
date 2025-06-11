# pages/Database.py
import os
import sqlite3
import pandas as pd
import streamlit as st
import tiktoken
import altair as alt
from utility_chat import *

DB_PATH = "data/sqdata.db"

# ⚙️ Debug Mode
DEBUG = os.getenv("DEBUG", "0") == "1"
if DEBUG:
    if "user_id" not in st.session_state:
        st.session_state["user_id"] = "Udebug123456"
        st.session_state["displayName"] = "U TEST"
        st.session_state["pictureUrl"] = "https://i.imgur.com/1Q9Z1Zm.png"
        st.session_state["status"] = "APPROVED"
        st.session_state["role"] = "super admin"
        st.info("🔧 Loaded mock user session for debugging.")

# 🔒 Permission check
if "role" not in st.session_state or st.session_state["role"] != "super admin":
    st.error("⛔️ คุณไม่มีสิทธิ์เข้าถึงหน้านี้ (เฉพาะ super admin เท่านั้น)")
    st.stop()


# 🔢 Token Counter
def count_tokens(text, model="gpt-4o"):
    try:
        enc = tiktoken.encoding_for_model(model)
    except:
        enc = tiktoken.get_encoding("cl100k_base")
    return len(enc.encode(text or ""))


# 📥 Fetch table data
def fetch_table(table_name):
    if not os.path.exists(DB_PATH):
        st.error(f"❌ ไม่พบไฟล์ฐานข้อมูล: {DB_PATH}")
        return pd.DataFrame()
    try:
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql_query(f"SELECT * FROM {table_name}", conn)
        conn.close()

        if table_name == "messages" and "content" in df.columns:
            df["token_count"] = df["content"].apply(lambda x: count_tokens(x))

        if "created_at" in df.columns:
            df["created_at"] = pd.to_datetime(
                df["created_at"], errors="coerce"
            ).dt.strftime("%Y-%m-%d %H:%M:%S")

        if "token_count" in df.columns:
            cols = [col for col in df.columns if col != "token_count"] + ["token_count"]
            df = df[cols]

        return df
    except sqlite3.OperationalError as e:
        st.error(f"❌ SQLite Error: {e}")
        return pd.DataFrame()


# 📊 Token Usage Summary
def summarize_token_usage(user_id=None):
    from utility_chat import init_db

    conn, cursor = init_db()

    query = """
        SELECT user_id, model,
               SUM(prompt_tokens) AS prompt_tokens,
               SUM(completion_tokens) AS completion_tokens,
               SUM(total_tokens) AS total_tokens
        FROM token_usage
    """
    if user_id:
        query += " WHERE user_id = ?"
        cursor.execute(query + " GROUP BY user_id, model", (user_id,))
    else:
        cursor.execute(query + " GROUP BY user_id, model")

    results = cursor.fetchall()
    if not results:
        st.info("ไม่พบข้อมูล token usage")
        return

    df = pd.DataFrame(
        results,
        columns=[
            "user_id",
            "model",
            "prompt_tokens",
            "completion_tokens",
            "total_tokens",
        ],
    )
    st.dataframe(df, use_container_width=True)

    pivoted = (
        df.pivot(index="user_id", columns="model", values="total_tokens")
        .fillna(0)
        .reset_index()
    )
    melted = pivoted.melt(
        id_vars=["user_id"], var_name="model", value_name="total_tokens"
    )

    chart = (
        alt.Chart(melted)
        .mark_bar()
        .encode(
            x=alt.X("user_id:N", title="ผู้ใช้"),
            y=alt.Y("total_tokens:Q", title="Token รวม"),
            color=alt.Color("model:N", title="โมเดล"),
            tooltip=["user_id", "model", "total_tokens"],
        )
    )

    st.altair_chart(chart, use_container_width=True)


# 🗂 Table list
TABLES = {
    "ผู้ใช้งาน (access_login)": "access_login",
    "บทสนทนา (conversations)": "conversations",
    "ข้อความ (messages)": "messages",
    "Prompts": "prompts",
    "ส่งออกแล้ว (sent_records)": "sent_records",
    "JSON ต้นฉบับ (raw_jsons)": "raw_json",
}

# 🧭 Sidebar menu
menu = st.sidebar.radio("เมนู", ["Backup/Restore db", "📊 ข้อมูลจากฐานข้อมูล"])

# 📊 Table viewer
if menu == "📊 ข้อมูลจากฐานข้อมูล":
    st.title("📊 ข้อมูลจากฐานข้อมูล")
    selected_label = st.selectbox("เลือกตาราง", list(TABLES.keys()))
    table_name = TABLES[selected_label]

    if (
        "last_table" not in st.session_state
        or st.session_state["last_table"] != table_name
    ):
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

    st.markdown("---")
    with st.expander("📊 รวม Token Usage Summary"):
        summarize_token_usage()

# 💾 Backup / Restore
elif menu == "Backup/Restore db":
    st.title("📦 Backup / Restore Database")
    st.warning(
        """
        ### ℹ️ คำแนะนำการใช้งาน Backup / Restore
        - สำรองข้อมูลก่อนทุกการเปลี่ยนแปลง
        - การ Restore จะเขียนทับไฟล์เดิมทันที
        """
    )
    backup1, backup2 = st.columns([1, 1])

    with backup1:
        st.subheader("📥 Backup Database")
        if os.path.exists(DB_PATH):
            with open(DB_PATH, "rb") as f:
                st.download_button(
                    label="⬇️ ดาวน์โหลด sqdata.db",
                    data=f,
                    file_name="sqdata.db",
                    mime="application/octet-stream",
                )
        else:
            st.error("❌ ไม่พบไฟล์ฐานข้อมูล: data/sqdata.db")

    with backup2:
        st.subheader("📤 Restore Database")
        uploaded_file = st.file_uploader("อัปโหลดไฟล์ .db", type=["db"])
        if uploaded_file is not None:
            confirm = st.checkbox(
                "⚠️ ยืนยันเขียนทับฐานข้อมูล", value=False, key="confirm_restore"
            )
            if st.button("♻️ Restore ทับฐานข้อมูล", disabled=not confirm):
                try:
                    with open(DB_PATH, "wb") as f:
                        f.write(uploaded_file.read())
                    st.success("✅ กู้คืนฐานข้อมูลเรียบร้อยแล้ว!")
                    st.info("🔄 กรุณา refresh หน้าแอปเพื่อโหลดข้อมูลใหม่")
                except Exception as e:
                    st.error(f"❌ เกิดข้อผิดพลาดขณะเขียนไฟล์: {e}")
