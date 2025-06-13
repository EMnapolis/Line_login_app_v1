import os
import sqlite3
import pandas as pd
import streamlit as st
import tiktoken
import altair as alt
from utility_chat import *
from utility_ai import *

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
def summarize_token_usage(user_id=None, default_quota=1_000_000):
    conn, cursor = init_db()

    # ✅ ดึงข้อมูล token usage
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

    # ✅ รวมยอด token ต่อ user
    usage_df = df.groupby("user_id", as_index=False)["total_tokens"].sum()
    usage_df = usage_df.rename(columns={"total_tokens": "รวม Token ที่ใช้"})

    # ✅ ดึง quota override จาก record ล่าสุดของแต่ละ user ที่มี quota_override
    cursor.execute(
        """
        SELECT user_id, quota_override
        FROM token_usage
        WHERE quota_override IS NOT NULL
        AND id IN (
            SELECT MAX(id) FROM token_usage
            WHERE quota_override IS NOT NULL
            GROUP BY user_id
        )
        """
    )
    quota_rows = cursor.fetchall()
    quota_dict = {uid: quota for uid, quota in quota_rows}

    # ✅ เพิ่มคอลัมน์ quota และ token คงเหลือ
    usage_df["โควตา Token"] = usage_df["user_id"].apply(
        lambda uid: quota_dict.get(uid, default_quota)
    )
    usage_df["Token คงเหลือ"] = usage_df["โควตา Token"] - usage_df["รวม Token ที่ใช้"]
    usage_df["% ที่ใช้แล้ว"] = (
        usage_df["รวม Token ที่ใช้"] / usage_df["โควตา Token"] * 100
    ).round(2)

    # ✅ แสดงผล
    st.dataframe(usage_df, use_container_width=True)

    with st.expander("📊 กราฟรวม Token ที่ใช้ (TOP 10)", expanded=False):
        top10 = usage_df.sort_values(by="รวม Token ที่ใช้", ascending=False).head(10)
        st.bar_chart(top10.set_index("user_id")["รวม Token ที่ใช้"])

    # ✅ คำนวณโควตา → คงเหลือ → เปอร์เซ็นต์
    def get_quota(uid):
        return quota_dict.get(uid, default_quota)

    usage_df["โควตา"] = usage_df["user_id"].apply(get_quota)
    usage_df["Token คงเหลือ"] = usage_df.apply(
        lambda row: max(row["โควตา"] - row["รวม Token ที่ใช้"], 0), axis=1
    )
    usage_df["% ใช้ไปแล้ว"] = (usage_df["รวม Token ที่ใช้"] / usage_df["โควตา"] * 100).round(
        2
    )

    # ✅ แสดงตารางและกราฟ
    st.markdown("### 📋 ตารางรวม Token ต่อผู้ใช้")
    st.dataframe(usage_df, use_container_width=True)

    # 🔽 กราฟ token usage ตามโมเดล
    pivoted = (
        df.pivot(index="user_id", columns="model", values="total_tokens")
        .fillna(0)
        .reset_index()
    )
    melted = pivoted.melt(
        id_vars=["user_id"], var_name="model", value_name="total_tokens"
    )

    st.markdown("### 📊 กราฟการใช้ Token ตามโมเดล")
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
menu = st.sidebar.radio(
    "เมนู", ["📊 ข้อมูลจากฐานข้อมูล", "ตรวจสอบ/จัดการ Token", "Backup/Restore db"]
)

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

# ✅ Token adjustment UI
elif menu == "ตรวจสอบ/จัดการ Token":
    st.header("🛠 จัดการ Token ของผู้ใช้")
    conn, cursor = init_db()

    # ────────────────
    # 🔹 1. ตั้งค่าโควตา Token
    # ────────────────
    st.subheader("🌟 กำหนดโควตา Token")

    cursor.execute("SELECT DISTINCT user_id FROM token_usage ORDER BY user_id")
    user_ids = [row[0] for row in cursor.fetchall()]

    if not user_ids:
        st.info("⚠️ ยังไม่มีข้อมูลผู้ใช้ในระบบ token_usage")
    else:
        selected_quota_user = st.selectbox(
            "เลือกผู้ใช้ที่ต้องการตั้งโควตา",
            user_ids,
            key="quota_user_selectbox",
        )

        new_quota = st.number_input(
            "🔄 กำหนด quota ใหม่ (ใส่จำนวนใหม่หรือลดก็ได้)",
            min_value=0,
            value=1_000_000,
            step=100_000,
        )

        if st.button("✅ บันทึก quota ใหม่"):
            try:
                now = pd.Timestamp.now().isoformat()
                cursor.execute(
                    """
                    INSERT INTO token_usage (
                        user_id, model, prompt_tokens, completion_tokens, total_tokens,
                        quota_override, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        selected_quota_user,
                        "quota",  # 📌 ใช้ model='quota' เพื่อบ่งชี้ว่าเป็นบรรทัด quota override
                        0,
                        0,
                        0,
                        new_quota,
                        now,
                    ),
                )
                conn.commit()
                st.success(
                    f"🌟 ปรับ quota ใหม่เป็น {new_quota:,} tokens ให้ `{selected_quota_user}` สำเร็จ"
                )
            except Exception as e:
                st.error(f"❌ เกิดข้อผิด: {e}")

    # ────────────────
    # 📅 2. รายงาน token รายวัน
    # ────────────────
    st.markdown("---")
    st.subheader("📅 รายงานการใช้ Token รายวัน")

    # 🔁 refresh user_ids อีกครั้งเผื่อมีการเพิ่มจาก quota ด้านบน
    user_ids = [r[0] for r in get_token_usage_summary(cursor)]
    if not user_ids:
        st.info("⚠️ ยังไม่มีข้อมูล token usage")
    else:
        selected_user = st.selectbox("เลือกผู้ใช้", user_ids, key="user_token_daily")

        cursor.execute(
            """
            SELECT DATE(created_at) AS วัน, SUM(total_tokens) AS tokens
            FROM token_usage
            WHERE user_id = ?
            GROUP BY DATE(created_at)
            ORDER BY DATE(created_at) DESC
            """,
            (selected_user,),
        )
        daily_data = cursor.fetchall()

        if daily_data:
            df_daily = pd.DataFrame(daily_data, columns=["วันที่", "รวม Token ที่ใช้"])
            st.dataframe(df_daily, use_container_width=True)
            st.bar_chart(df_daily.set_index("วันที่"))
        else:
            st.info("📭 ยังไม่มีข้อมูล Token รายวันสำหรับผู้ใช้นี้")

    # ────────────────
    # 📊 3. Token Usage Summary
    # ────────────────
    st.markdown("---")
    st.subheader("📊 สรุปภาพรวมการใช้ Token")

    usage_df = summarize_token_usage()
    if usage_df is not None:
        with st.expander("📈 กราฟรวม Token ที่ใช้ (TOP 10)", expanded=False):
            top10 = usage_df.sort_values(by="รวม Token ที่ใช้", ascending=False).head(10)
            st.bar_chart(top10.set_index("user_id")["รวม Token ที่ใช้"])

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
