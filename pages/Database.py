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

# Left Pane Menu
menu = st.sidebar.radio("เมนู", ["📊 ข้อมูลจากฐานข้อมูล", "Backup/Restore db"])

if menu == "📊 ข้อมูลจากฐานข้อมูล":
    st.title("📊 ข้อมูลจากฐานข้อมูล")

    selected_label = st.selectbox("เลือกตาราง", list(TABLES.keys()))
    table_name = TABLES[selected_label]
    df = fetch_table(table_name)

    if df.empty:
        st.warning("⚠️ ไม่พบข้อมูลในตาราง หรือเกิดข้อผิดพลาดระหว่างอ่านข้อมูล")
    else:
        ROWS_PER_PAGE = 50  # จำนวนแถวต่อหน้า
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
elif menu == "Backup/Restore db":
    st.header("Backup/Restore db")
    st.warning("""
        ⚠️ **คำเตือนเกี่ยวกับการสำรองและกู้คืนฐานข้อมูล**

        การดำเนินการในหน้านี้จะเกี่ยวข้องกับไฟล์ฐานข้อมูล (`sqdata.db`) ซึ่งเป็นที่เก็บข้อมูลหลักทั้งหมดของระบบ:

        - ปุ่ม **"ดาวน์โหลดสำเนา DB"** จะทำการสำรองข้อมูลทั้งหมด ณ ขณะนั้นออกเป็นไฟล์ `.db` เพื่อเก็บไว้ใช้ในอนาคต
        - หากคุณ **อัปโหลดไฟล์ฐานข้อมูล (.db)** ที่มีอยู่ ระบบจะ **เขียนทับฐานข้อมูลปัจจุบันทันที** ซึ่งอาจทำให้ข้อมูลใหม่หายไปถาวร

        🔐 **คำแนะนำสำหรับผู้ใช้งานทั่วไป**:
        - ก่อนอัปโหลดไฟล์ `.db` ทุกครั้ง ควรดาวน์โหลดข้อมูลล่าสุดเก็บไว้ก่อน
        - ตรวจสอบว่าไฟล์ที่นำกลับมาใช้นั้นเป็นไฟล์ที่เชื่อถือได้และผ่านการสำรองไว้ล่าสุด

        ✅ กระบวนการนี้เหมาะสำหรับการโอนย้ายข้อมูลระหว่างการ deploy หรือการกู้คืนจากสำเนาสำรองในกรณีฉุกเฉิน
        """)
    backup1, backup2 = st.columns([2,3])
    with backup1:
        #ทำปุ่ม Backup sqdata.db มาเก็บไว้
        st.info("ดาวน์โหลดสำเนา sqdata.db")
        with open("data/sqdata.db", "rb") as f:
            st.download_button("💾 ดาวน์โหลดสำเนา DB", f.read(), file_name="sqdata_backup.db")
    with backup2:
        upload = st.file_uploader("📤 อัปโหลดไฟล์ฐานข้อมูล sqdata.db", type=["db"])
        if upload:
            with open("data/sqdata.db", "wb") as f:
                f.write(upload.getbuffer())
            st.success("อัปโหลดเรียบร้อย และข้อมูลถูกคืนค่า")
    # # ✅ เพิ่มปุ่มแสดง JSON ถ้าเป็นตาราง raw_json
    # if table_name == "raw_json" and "response_json" in df.columns and df["response_json"].notna().any():
    #     st.markdown("---")
    #     st.subheader("🔍 ตรวจสอบ JSON ต้นฉบับ")

    #     for i, row in df.iterrows():
    #         if pd.notna(row["response_json"]):
    #             label = f"🧾 แถว {i}"
    #             if "message_id" in row:
    #                 label += f" | message_id: {row['message_id']}"

    #             with st.expander(label):
    #                 try:
    #                     st.json(json.loads(row["response_json"]))
    #                 except Exception:
    #                     st.code(row["response_json"])

