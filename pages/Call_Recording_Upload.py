# pages/Call_Recording_Upload.py
import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
import os
from call_upload_utils import (
    vl3cx_login, vl3cx_refresh_token,
    fetch_json, process_records, load_sent_rec_ids_db,
    download_recording, upload_file_to_asb,
    create_chat_room, json_helper, save_sent_rec_id_db, log_failed
)
from utility_chat import *

CHAT_TOKEN_VL = os.getenv("CHAT_TOKEN") or "Empty" #Set ตัวแปร chat_token_vl

DB_FILE = os.path.join("data", "sqdata.db")
def get_connection():
    return sqlite3.connect(DB_FILE)

# ----------------------------
# ⚙️ Debug Mode Configuration
# ----------------------------
DEBUG = os.getenv("DEBUG", "0") == "1"

if DEBUG:
    # ตั้งค่า session ผู้ใช้ mock สำหรับการทดสอบ
    if "user_id" not in st.session_state:
        st.session_state["user_id"] = "Udebug123456"
        st.session_state["displayName"] = "ทดสอบระบบ TEST"
        st.session_state["pictureUrl"] = "https://i.imgur.com/1Q9Z1Zm.png"
        st.session_state["status"] = "APPROVED"
        st.session_state["role"] = "super admin"
        st.info("🔧 Loaded mock user session for debugging.")

# ========== Role ==========
role = st.session_state.get("role", "").lower()
# "super admin" , "admin" , "user"

# ตั้งค่าเริ่มต้น session_state ให้ปลอดภัย
# ป้องกัน KeyError หรือ AttributeError โดยตั้งค่าก่อน
for key in ["access_token", "refresh_token", "tmp_token"]:
    if key not in st.session_state:
        st.session_state[key] = ""

#เริ่มต้นการทำงานของหน้า pages/Call_Recording_Upload.py
st.set_page_config(page_title="ระบบ Call Recording Upload", page_icon="🎙️", layout="wide")
st.page_link("app.py", label="⬅️ กลับหน้าหลัก", icon="🏠")
st.title("🎙️ ระบบ Call Recording Upload")

#---------------
# ✅ ตรวจ login และสิทธิ์
if "user_id" not in st.session_state or st.session_state.get("status") != "APPROVED":
    st.error("🚫 กรุณาเข้าสู่ระบบ และรอการอนุมัติ")
    st.stop()
#---------------

# Left Pane Menu
menu = st.sidebar.radio("เมนู", ["หน้าคำสั่งทำงาน", "คุณสมบัติของโปรแกรม", "วิธีการใช้งาน"])

if menu == "หน้าคำสั่งทำงาน":
    with st.expander("🔐 ขยายเพื่อแก้ไข Tmp Token ระบบ Villa 3CX", expanded=False):
        vl3cx1, vl3cx2, vl3cx3, vl3cx4 = st.columns([3,2,3,2])
        with vl3cx1:
            if st.button("Villa3CXLogin"):
                access_token, refresh_token = vl3cx_login()
                if access_token and refresh_token:
                    st.session_state.access_token = access_token
                    st.session_state.refresh_token = refresh_token
                    st.session_state.login_status = "✅ Login success!"
                else:
                    st.session_state.login_status = "❌ Login failed."
        with vl3cx2:
            if "login_status" in st.session_state:
                st.markdown(st.session_state.login_status)

        with vl3cx3:
            if st.button("Refresh Token"):
                if st.session_state.refresh_token:
                    new_token = vl3cx_refresh_token(st.session_state.refresh_token)
                    if new_token:
                        st.session_state.tmp_token = new_token
                        st.session_state.refresh_status = "✅ Token refreshed!"
                    else:
                        st.session_state.refresh_status = "❌ Refresh failed."
                else:
                    st.session_state.refresh_status = "⚠️ Login first."
        with vl3cx4:
            if "refresh_status" in st.session_state:
                st.markdown(st.session_state.refresh_status)

        tmp_token = st.text_input("3CX Temporary Access Token (tmp_token)",
                                value=st.session_state.tmp_token, type="password",
                                help="กรอก tmp_token จาก 3CX Dashboard (ดูวิธีใน 'วิธีการใช้งาน')")

    with st.expander("🔐 ขยายเพื่อแก้ไข Chat Token และ Contact ID", expanded=False):
        chat_token = st.text_input("ChatCenter Access Token (chat_token)",
                                   value = CHAT_TOKEN_VL,type="password",
                                   help="กรอก chat_token ที่ได้รับจาก https://cc-stg.villa-marketjp.com")
        contact_id = st.number_input("Contact ID", value=3)
    chat_tk1, chat_tk2, chat_tk3 = st.columns([2,3,5]) # แบ่งคอลัมน์ให้แสดงผล 
    with chat_tk1:
        # --- 🔁 เริ่มต้นใหม่: Clear session state ทั้งหมด ---
        if st.button("🔁 **เริ่มใหม่**", disabled=st.session_state.get("is_processing", False)):
            for key in ["ready_to_process", "processed", "df_new"
                    , "processed_df","full_df", "selected_ids"]:
                st.session_state.pop(key, None)
                
                
            st.rerun()
    with chat_tk2:
        mode = st.radio("**เลือกโหมดการทำงาน**", ["ดึงข้อมูลจากวันที่"])
    with chat_tk3:
        st.markdown("""
        1️⃣ **กรอก Token และช่วงวันที่ที่ต้องการดึงข้อมูล**  
        2️⃣ กดปุ่ม 📥 **ดึงข้อมูล JSON จาก 3CX**  
        3️⃣ กดปุ่ม 🚀 **เริ่มประมวลผลรายการใหม่**
        """)

    if mode == "ดึงข้อมูลจากวันที่":

        # ให้ผู้ใช้เลือกวันที่เริ่มต้น และวันที่สิ้นสุด
        before_date = date.today() - timedelta(days=1)
        default_date = date.today()
        mode_col1, mode_col2,mode_col3 = st.columns(3)  # แบ่งคอลัมน์ให้เลือกวันที่แบบคู่
        with mode_col1:
            from_date = st.date_input("From Date", value=before_date) # วันที่เริ่มต้น
        with mode_col2:
            to_date = st.date_input("To Date", value=default_date)  # วันที่สิ้นสุด
        with mode_col3:
            st.markdown("""
                            <div style="display: flex; flex-direction: column; align-items: left; justify-content: left; height: 100%;">
                                <span style="font-size: 14px; margin-bottom: 5px;">ปุ่มคำสั่ง</span>
                            </div>
                            """, unsafe_allow_html=True)
            # ปุ่มสั่งดึงข้อมูล JSON จาก 3CX
            if st.button("📥 ดึงข้อมูล JSON จาก 3CX", disabled=st.session_state.get("is_processing", False)):
                
                if not tmp_token or not chat_token:
                    st.error("กรุณาใส่ทั้ง tmp_token และ chat_token")
                else:
                    with st.spinner("กำลังดึงข้อมูล JSON จาก 3CX..."):
                        json_data = fetch_json(tmp_token, from_date, to_date)
                        df = pd.json_normalize(json_data.get("value", []))

                    if df.empty:
                        st.warning("ไม่มีข้อมูลจาก 3CX API ในช่วงเวลาที่เลือก")
                    else:
                        df["Id"] = df["Id"].astype(str)
                        sent_ids = load_sent_rec_ids_db()
                        df["already_sent"] = df["Id"].isin(sent_ids)

                        # 🕑 แปลงเวลา และสร้างข้อความ preview
                        def build_message(row):
                            try:
                                rec_id = row["Id"]
                                start_time_utc = datetime.strptime(row["StartTime"], "%Y-%m-%dT%H:%M:%S.%fZ")
                                local_time = start_time_utc + timedelta(hours=7)
                                start_time_str = local_time.strftime("%Y-%m-%d %H:%M:%S")

                                from_num = row["FromCallerNumber"].replace("Ext.", "")
                                to_num = row["ToCallerNumber"]
                                from_display = row["FromDisplayName"]
                                to_display = row["ToDisplayName"]
                                call_type = row["CallType"]

                                if call_type == "InboundExternal":
                                    from_display_clean = from_display.split(":")[-1] if ":" in from_display else from_display
                                    return f"From_{from_num}_{from_display_clean}_To_{to_num}_{to_display}_เมื่อ_{start_time_str}"
                                else:
                                    to_display_clean = "" if to_num == to_display else to_display
                                    msg = f"From_{from_num}_{from_display}_To_{to_num}"
                                    if to_display_clean:
                                        msg += f"_{to_display_clean}"
                                    return f"{msg}_เมื่อ_{start_time_str}"
                            except:
                                return "❌ สร้างข้อความไม่สำเร็จ"

                        df["preview_message"] = df.apply(build_message, axis=1)

                        st.session_state["full_df"] = df
                        st.session_state["selected_ids"] = []  # Reset selection
               
    if "full_df" in st.session_state:
        df = st.session_state["full_df"]

        # 🔍 ส่วนค้นหาและกรองประเภทสาย
        search1, search2, search3 = st.columns([1, 1, 1])
        with search1:   # 🔎 ค้นหาจาก rec_id หรือ preview
            search_text = st.text_input("🔎 ค้นหา rec_id หรือข้อความสรุปสาย", value="")
        with search2:   # 📞 ตัวกรองประเภทสาย
            call_type_filter = st.selectbox("📞 ประเภทสาย", options=["ทั้งหมด", "InboundExternal", "OutboundExternal"])
        with search3:   # 🧹 เริ่มต้นด้วยสำเนา DataFrame
            filtered_df = df.copy()

            # กรองด้วยข้อความค้นหา
            if search_text:
                search_lower = search_text.lower()
                filtered_df = filtered_df[
                    filtered_df["Id"].str.lower().str.contains(search_lower) |
                    filtered_df["preview_message"].str.lower().str.contains(search_lower)
                ]
            # กรองด้วยประเภทสาย
            if call_type_filter != "ทั้งหมด":
                filtered_df = filtered_df[filtered_df["CallType"] == call_type_filter]

            # ✅ FIX BUG: ตรวจว่าข้อมูลว่าง
            total_rows = len(filtered_df)
            if total_rows == 0:
                st.warning("⚠️ ไม่พบข้อมูลที่ตรงกับเงื่อนไข")
                st.stop()

            # แสดงผลแบบแบ่งหน้า
            ROWS_PER_PAGE = 50
            total_pages = (total_rows - 1) // ROWS_PER_PAGE + 1

            # 🧭 แสดงตัวเลือกหน้า (fix max_value)
            page = st.number_input(
                    "เลือกหน้า",
                    min_value=1,
                    max_value=max(1, total_pages),
                    value=1,
                    step=1
                )
            start_idx = (page - 1) * ROWS_PER_PAGE
            end_idx = start_idx + ROWS_PER_PAGE
            paginated_df = filtered_df.iloc[start_idx:end_idx]

        # 🧾 แสดงจำนวนแถวและหน้าที่กำลังดู
        st.caption(f"🔢 แสดงหน้า {page} จาก {total_pages} | รวมทั้งหมด {total_rows} แถว")

        # ✅ ปุ่มจัดการ selection
        button_col1, button_col2, button_col3, button_col4 = st.columns([5, 4, 6, 6])
        with button_col1:
            if st.button("🔘 เลือกทั้งหมด (ทุกหน้า)", disabled=st.session_state.get("is_processing", False)):
                st.session_state["selected_ids"] = filtered_df[~filtered_df["already_sent"]]["Id"].tolist()
        with button_col2:
            if st.button("🔘 ยกเลิกทั้งหมด", disabled=st.session_state.get("is_processing", False)):
                st.session_state["selected_ids"] = []
        with button_col3:
            if st.button("🔘 เลือกเฉพาะหน้านี้", disabled=st.session_state.get("is_processing", False)):
                page_ids = paginated_df[~paginated_df["already_sent"]]["Id"].tolist()
                st.session_state["selected_ids"] = list(set(st.session_state["selected_ids"] + page_ids))
        with button_col3:
            st.markdown("")

        # ✅ แสดง checkbox สำหรับแต่ละรายการ
        for _, row in paginated_df.iterrows():
            rec_id = row["Id"]
            preview = row["preview_message"]
            already_sent = row["already_sent"]
            default_checked = rec_id in st.session_state["selected_ids"]

            if already_sent:
                st.markdown(f"✅ **{rec_id}**: {preview}")
            else:
                checked = st.checkbox(
                    f"🆕 {rec_id}: {preview}",
                    key=f"chk_{rec_id}",
                    value=default_checked
                )
                if checked and rec_id not in st.session_state["selected_ids"]:
                    st.session_state["selected_ids"].append(rec_id)
                elif not checked and rec_id in st.session_state["selected_ids"]:
                    st.session_state["selected_ids"].remove(rec_id)
        
        #แสดงจำนวนรายการที่เลือกก่อนเริ่ม
        selected_ids = st.session_state.get("selected_ids", [])
        st.info(f"📋 พบรายการที่เลือก: {len(selected_ids)} รายการ")
    
    # ปุ่มเริ่มประมวลผล
    if st.button("🚀 เริ่มประมวลผลรายการใหม่", disabled=st.session_state.get("is_processing", False)):
        if not tmp_token or not chat_token:
            st.error("กรุณาใส่ทั้ง tmp_token และ chat_token")
        elif not selected_ids:
            st.warning("กรุณาเลือกรายการ rec_id อย่างน้อยหนึ่งรายการ")
        else:
            st.session_state["is_processing"] = True

            selected_df = st.session_state["full_df"]
            selected_df = selected_df[selected_df["Id"].isin(selected_ids)]

            st.info(f"📋 กำลังประมวลผล {len(selected_df)} รายการ...")

            # ✅ แสดง progress bar
            progress = st.progress(0, text="⏳ กำลังประมวลผล...")

            try:
                # ❗ ใช้ logic เดิม (process_records ทำ loop อยู่แล้ว)
                processed_df = process_records(selected_df, tmp_token, chat_token, contact_id)
                st.session_state["processed"] = True
                st.session_state["processed_df"] = processed_df
                st.success("🎉 ประมวลผลเสร็จสิ้นแล้ว!")
            except Exception as e:
                st.error("❌ เกิดข้อผิดพลาดระหว่างประมวลผล")
                st.exception(e)

            progress.progress(1.0, text=f"✅ ประมวลผล {len(selected_df)} รายการเรียบร้อยแล้ว")
            st.session_state["is_processing"] = False


    # สร้างปุ่มให้ดาวน์โหลดไฟล์ผลลัพธ์ที่ประมวลผลแล้วในรูปแบบ CSV เมื่อประมวลผลเสร็จ
    if st.session_state.get("processed"):
        st.success("🎉 ประมวลผลเสร็จสิ้น")
        if role == "super admin":
            st.download_button(
                label="📥 ดาวน์โหลดผลลัพธ์เป็น CSV",     # ป้ายปุ่ม
                data=st.session_state["processed_df"].to_csv(index=False),    # แปลง DataFrame เป็น CSV
                file_name="processed_results.csv",  # ตั้งชื่อไฟล์ดาวน์โหลด
                mime="text/csv"                     # ระบุ MIME type สำหรับไฟล์ CSV
            )

elif menu == "คุณสมบัติของโปรแกรม":
    st.header("คุณสมบัติของโปรแกรม")
    st.markdown("""
    - ดึงข้อมูลจาก API 3CX ตามช่วงเวลาที่กำหนด
    - ดาวน์โหลดไฟล์เสียง และอัปโหลดเข้าสู่ระบบ
    - สร้างห้องสนทนาและส่งข้อความเสียงและข้อความประกอบเข้า ChatCenter
    - ตรวจสอบและป้องกันการส่งข้อมูลซ้ำด้วยการบันทึก `recId`

    ### 🔑 Token และข้อมูลที่ต้องกรอก
    - `tmp_token` (ใช้กับ API 3CX)
    - `chat_token` (ใช้กับ ChatCenter)
    - `contact_id` (ใช้กับ Upload และ CreateRoom)

    ### 🔁 Workflow สรุป (เริ่มจาก JSON)
    - กรอก `tmp_token`, `chat_token`, `contact_id`, วันที่เริ่ม/สิ้นสุด
    - ดึง JSON ด้วย curl API จาก 3CX ตามช่วงเวลา
    - โหลด JSON → DataFrame → กรองเฉพาะ recId ที่ยังไม่เคยส่ง
    - วนลูป: ดาวน์โหลดเสียง, อัปโหลด, สร้างห้อง, ส่งข้อความ
    - บันทึก recId ที่สำเร็จใส่ `sent_records.csv`

    ### 📁 โครงสร้างโปรเจกต์
    ```
    📁 project-root/
    ├── main.py                ← Streamlit app
    ├── utils.py               ← ฟังก์ชันสำหรับทุก API
    ├── logs/
    │   ├── sent_records.csv   ← เก็บ recId ที่สำเร็จแล้ว
    │   └── errors.csv         ← เก็บ recId ที่ error (ถ้ามี)
    ├── tmp/
    │   └── *.wav              ← ไฟล์เสียงชั่วคราว
    ```
    """)

elif menu == "วิธีการใช้งาน":
    st.header("📘 วิธีใช้งานระบบบันทึกเสียง 3CX")

    st.subheader("วิธีใช้งาน")
    st.markdown("""
    1️⃣ **กรอก Token และช่วงวันที่ที่ต้องการดึงข้อมูล**  
    2️⃣ กดปุ่ม 📥 **ดึงข้อมูล JSON จาก 3CX**  
    3️⃣ ระบบจะแสดงสรุปผล:  
    > ทั้งหมด: `185` รายการ | เคยส่งแล้ว: `184` | รอประมวลผล: `1`

    4️⃣ หากมีรายการ "รอประมวลผล" ให้กดปุ่ม 🚀 **เริ่มประมวลผลรายการใหม่**  
    5️⃣ ระบบจะประมวลผล ดาวน์โหลดไฟล์เสียง และส่งข้อความเข้าสู่ ChatCenter โดยอัตโนมัติ  
    6️⃣ คุณสามารถดาวน์โหลดผลลัพธ์เป็น CSV ได้หลังเสร็จสิ้น
    """)

    st.subheader("🛠 วิธีแก้ไขปัญหา: Invalid JSON returned! Status: 401")
    st.markdown("""
    หากพบข้อความ **Exception: Invalid JSON returned! Status: 401** แสดงว่า token หมดอายุหรือไม่ถูกต้อง  
    ให้ทำตามขั้นตอนดังนี้:

    1. เข้าเว็บ [3CX Dashboard](https://villamarket.3cx.co/#/office/dashboard) และ Login  
    2. กด `F12` เพื่อเปิด Developer Tools แล้วเลือกแท็บ **Network**  
    3. ไปที่เมนู **Recordings** [คลิกที่นี่](https://villamarket.3cx.co/#/office/recordings)  
    4. คลิกที่รายการคำขอ (Request) ใดๆ ในแท็บ Network > ไปที่ **Headers**  
    5. ค้นหา `authorization: Bearer` แล้วคัดลอกเฉพาะ **token ที่ขึ้นต้นด้วย `ey...`**  
    6. นำ token ที่ได้ไปกรอกในช่อง `tmp_token` ของหน้าโปรแกรม
    """)

    st.info("💡 เคล็ดลับ: Token มีอายุจำกัด หากระบบแจ้ง Error ให้ดึงใหม่ตามขั้นตอนข้างต้น")


# Footer ด้านล่างสุด
st.markdown("""
    <hr style='margin-top: 3rem;'>
    <div style='text-align: center; color: gray;'>
        Provide ระบบสำหรับ วิลล่า มาร์เก็ตเจพี โดยยูนิคอร์น เทค อินทริเกรชั่น
    </div>
""", unsafe_allow_html=True)