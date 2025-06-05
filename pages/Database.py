#pages/Database.py
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
    st.stop()  # 🛑 หยุดการทำงานหน้านี้ทั้งหมด

def count_tokens(text, model="gpt-3.5-turbo"):
    try:
        enc = tiktoken.encoding_for_model(model)
    except:
        enc = tiktoken.get_encoding("cl100k_base")  # fallback
    return len(enc.encode(text or ""))

def fetch_table(table_name):
    if not os.path.exists(db_path):
        st.error(f"❌ ไม่พบไฟล์ฐานข้อมูล: {db_path}")
        return pd.DataFrame()
    try:
        conn = sqlite3.connect(db_path)
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
    "ส่งออกแล้ว (sent_records)": "sent_records",
    "JSON ต้นฉบับ (raw_jsons)": "raw_json"
}

st.title("📊 ข้อมูลจากฐานข้อมูล")

selected_label = st.selectbox("เลือกตาราง", list(TABLES.keys()))
table_name = TABLES[selected_label]
df = fetch_table(table_name)

if df.empty:
    st.warning("⚠️ ไม่พบข้อมูลในตาราง หรือเกิดข้อผิดพลาดระหว่างอ่านข้อมูล")
else:
    ROWS_PER_PAGE = 20  # จำนวนแถวต่อหน้า
    total_rows = len(df)
    total_pages = (total_rows - 1) // ROWS_PER_PAGE + 1

    datacol1, datacol2, datacol3 = st.columns([4, 4, 2])
    with datacol1:
        st.markdown("""
                <div style="display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100%;">
                    <span style="font-size: 14px; margin-bottom: 8px;"> </span>
                </div>
                """, unsafe_allow_html=True)
    with datacol2:
        st.markdown("""
                <div style="display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100%;">
                    <span style="font-size: 14px; margin-bottom: 8px;"> </span>
                </div>
                """, unsafe_allow_html=True)
    with datacol3:
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
                    

