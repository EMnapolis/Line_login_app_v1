# import streamlit as st

# st.set_page_config(page_title="อัปโหลดไฟล์เสียง", page_icon="🎧")

# st.title("🎧 ระบบอัปโหลด Call Recording")
# st.write("หน้านี้ใช้สำหรับอัปโหลดไฟล์บันทึกเสียง")

# pages/1_Call_Recording_Upload.py
import streamlit as st
import pandas as pd
import datetime
import os
from call_upload_utils import (
    fetch_json, process_records, load_sent_rec_ids,
    download_recording, upload_file_to_asb,
    create_chat_room, json_helper, save_sent_rec_id, log_failed
)
from config import CHAT_TOKEN

#def render_page():
st.page_link("app.py", label="⬅️ กลับหน้าหลัก", icon="🏠")
st.title("🎙️ ระบบ Call Recording Upload")
#---------------
# ✅ ตรวจ login และสิทธิ์

# Login Test
if "user_id" not in st.session_state or st.session_state.get("status") != "APPROVED":
    st.error("🚫 กรุณาเข้าสู่ระบบ และรอการอนุมัติ")
    st.stop()
#---------------

# Header ด้านบนขวา
st.markdown("""
    <div style='position: absolute; top: 1rem; right: 2rem; font-size: 20px; font-weight: bold;'>
        Python Recording Upload
    </div>
""", unsafe_allow_html=True)

# Left Pane Menu
menu = st.sidebar.radio("เมนู", ["หน้าคำสั่งทำงาน", "คุณสมบัติของโปรแกรม", "วิธีติดตั้ง และการใช้งาน"])

if menu == "หน้าคำสั่งทำงาน":
    #st.title("VillaMarket Call Recording Processor")

    tmp_token = st.text_input("3CX Temporary Access Token (tmp_token)",
                              value="", type="password",
                              help="กรอก tmp_token จาก 3CX Dashboard (ดูวิธีใน 'วิธีติดตั้ง และการใช้งาน')")

    # st.markdown("<small><b>ChatCenter Access Token (chat_token)</b></small>", unsafe_allow_html=True)
    with st.expander("🔐 ขยายเพื่อแก้ไข Chat Token และ Contact ID", expanded=False):
        chat_token = st.text_input("ChatCenter Access Token (chat_token)",
                                   value=CHAT_TOKEN,
                                   type="password")
        contact_id = st.number_input("Contact ID", value=3)
    col1, col2, col3 = st.columns([1,3,4]) # แบ่งคอลัมน์ให้แสดงผล
    with col1:
        # --- 🔁 เริ่มต้นใหม่: Clear session state ทั้งหมด ---
        if st.button("🔁 **เริ่มใหม่**"):
            for key in ["ready_to_process", "processed", "df_new", "processed_df"]:
                st.session_state.pop(key, None)
            st.rerun()
    with col2:
        mode = st.radio("**เลือกโหมดการทำงาน**", ["ดึงข้อมูลจากวันที่", "ประมวลผลจาก recId โดยตรง"])
    with col3:
        st.markdown("""
    1️⃣ **กรอก Token และช่วงวันที่ที่ต้องการดึงข้อมูล**  
    2️⃣ กดปุ่ม 📥 **ดึงข้อมูล JSON จาก 3CX**  
    3️⃣ กดปุ่ม 🚀 **เริ่มประมวลผลรายการใหม่**
        """)

    if mode == "ดึงข้อมูลจากวันที่":

        # ให้ผู้ใช้เลือกวันที่เริ่มต้น และวันที่สิ้นสุด
        before_date = datetime.date.today() - datetime.timedelta(days=1)
        default_date = datetime.date.today()
        col1, col2 = st.columns(2)  # แบ่งคอลัมน์ให้เลือกวันที่แบบคู่
        with col1:
            from_date = st.date_input("From Date", value=before_date) # วันที่เริ่มต้น
        with col2:
            to_date = st.date_input("To Date", value=default_date)  # วันที่สิ้นสุด

        # ปุ่มสั่งดึงข้อมูล JSON จาก 3CX
        if st.button("📥 ดึงข้อมูล JSON จาก 3CX"):
            # ตรวจสอบว่ามี token ทั้งสองหรือไม่
            if not tmp_token or not chat_token:
                st.error("กรุณาใส่ทั้ง tmp_token และ chat_token")
            else:
                # เรียกฟังก์ชัน fetch_json เพื่อดึงข้อมูล JSON จาก API โดยใช้ tmp_token และช่วงวันที่
                with st.spinner("กำลังดึงข้อมูล JSON จาก 3CX..."):
                    json_data = fetch_json(tmp_token, from_date, to_date) # ดึง JSON จาก 3CX
                    df = pd.json_normalize(json_data.get("value", [])) # แปลง JSON เป็น DataFrame

                # ตรวจสอบว่าได้ข้อมูลกลับมามั้ย ถ้าไม่มีข้อมูล
                if df.empty:
                    st.warning("ไม่มีข้อมูลจาก 3CX API ในช่วงเวลาที่เลือก")
                else:
                    total_count = len(df) # จำนวนข้อมูลทั้งหมดที่ได้มา
                    sent_ids = load_sent_rec_ids() # โหลด recId ที่เคยส่งไปแล้ว
                    df["Id"] = df["Id"].astype(str) # แปลงให้เป็น string เพื่อเปรียบเทียบ
                    df_new = df[~df["Id"].isin(sent_ids)] # กรองรายการที่ยังไม่เคยส่ง
                    new_count = len(df_new) # จำนวนที่ยังไม่เคยส่ง
                    old_count = total_count - new_count # จำนวนที่เคยส่งแล้ว

                    # เก็บข้อมูลไว้ใน session สำหรับนำไปประมวลผล
                    st.session_state["df_new"] = df_new
                    st.session_state["ready_to_process"] = new_count > 0

                    # แสดงผลลัพธ์ว่าเจอทั้งหมดกี่รายการ และมีกี่รายการที่ยังไม่เคยส่ง
                    st.info(f"🔢 ทั้งหมด: {total_count} รายการ | ✅ เคยส่งแล้ว: {old_count} | 🆕 รอประมวลผล: {new_count}")

    elif mode == "ประมวลผลจาก recId โดยตรง":
        rec_id = st.text_input("กรุณาใส่ recId")
        if st.button("🚀 ดำเนินการจาก recId"):
            if not tmp_token or not chat_token:
                st.error("กรุณาใส่ทั้ง tmp_token และ chat_token")
            elif not rec_id:
                st.error("กรุณาใส่ recId")
            else:
                # โหลดรายการ rec_id ที่เคยส่งไปแล้ว เพื่อไม่ให้ทำซ้ำ
                sent_ids = load_sent_rec_ids()
                if rec_id in sent_ids:
                    st.info("✅ recId นี้เคยถูกส่งไปแล้ว")
                else:
                    df_new = pd.DataFrame([{"Id": rec_id}])
                    st.session_state["df_new"] = df_new
                    st.session_state["ready_to_process"] = True
                    st.success("🎯 พบ recId และพร้อมประมวลผล")

# ตรวจสอบว่า session_state มีคีย์ "ready_to_process" และค่าคือ True หรือไม่ (มีข้อมูลพร้อมให้ประมวลผล)
if st.session_state.get("ready_to_process") and not st.session_state.get("processed"): #เงื่อนไข and น่าจะทำให้คลิีกปุ่มแล้วไม่ทำงานอะไร
    df_new = st.session_state["df_new"]  # ดึง DataFrame รายการใหม่ที่ยังไม่เคยส่งออกมาจาก session
    # st.info(f"📦 พร้อมประมวลผล {len(df_new)} รายการใหม่")   # แสดงจำนวนรายการใหม่ที่พร้อมประมวลผล

    # ปุ่มเริ่มประมวลผล
    if st.button("🚀 เริ่มประมวลผลรายการใหม่"):
        # เรียกฟังก์ชัน process_records เพื่อประมวลผลข้อมูล โดยใช้ df_new และ token ต่าง ๆ
        processed_df = process_records(df_new, tmp_token, chat_token, contact_id)
        st.session_state["processed"] = True   # บันทึกสถานะว่าได้ประมวลผลแล้ว
        st.session_state["processed_df"] = processed_df
        st.rerun()  # 🔄 รีเฟรชหน้าใหม่เพื่อซ่อนปุ่ม  คอมเมนท์ไว้ ก่อน


# สร้างปุ่มให้ดาวน์โหลดไฟล์ผลลัพธ์ที่ประมวลผลแล้วในรูปแบบ CSV เมื่อประมวลผลเสร็จ
if st.session_state.get("processed"):
    st.success("🎉 ประมวลผลเสร็จสิ้น")
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

elif menu == "วิธีติดตั้ง และการใช้งาน":
    st.header("📘 วิธีติดตั้งและการใช้งานระบบบันทึกเสียง 3CX")

    st.subheader("ขั้นตอนการติดตั้ง")
    st.markdown("""
    ✅ **1. ติดตั้ง Python 3**  
    ดาวน์โหลดจาก [python.org](https://www.python.org/downloads/) และติดตั้งให้เรียบร้อย

    ✅ **2. ติดตั้งไลบรารีที่จำเป็น**  
    เปิด Command Prompt หรือ Terminal แล้วพิมพ์:  
    ```bash
    pip install streamlit pandas requests
    ```

    ✅ **3. เปิดใช้งานโปรแกรม**  
    ดับเบิลคลิกที่ไฟล์ `run_streamlit.bat` เพื่อเปิดหน้าเว็บแอปพลิเคชัน
    """)

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

    st.subheader("🐞 วิธีแก้ปัญหา: โปรแกรมไม่ได้ติดตั้งที่ C:\\Villa\\Python Recording Upload")
    st.markdown("""
    หากคุณ **ย้ายโฟลเดอร์โปรแกรมไปไว้ที่ตำแหน่งอื่น** หรือไม่ได้ติดตั้งไว้ที่ `C:\\Villa\\Python Recording Upload`  
    อาจพบว่า **ดับเบิลคลิก `run_streamlit.bat` แล้วโปรแกรมไม่เปิด** หรือเปิดแล้วไม่พบไฟล์ `main.py`

    ✅  **วิธีแก้ไข:** 
    1. คลิกขวาที่ไฟล์ `run_streamlit.bat` แล้วเลือก **Edit**  
    2. แก้ไขบรรทัดนี้ (บรรทัดที่ 2):
    ```bat
    cd /d "C:\\Villa\\Python Recording Upload"
    ```
    > ให้เปลี่ยนเป็น **ตำแหน่งที่แท้จริงของโฟลเดอร์ที่คุณเก็บโปรแกรมไว้** เช่น:
    ```bat
    cd /d "D:\\MyProjects\\3CX_Uploader"
    ```

    3. บันทึกไฟล์ แล้วลองดับเบิลคลิกใหม่อีกครั้ง

    """)



# Footer ด้านล่างสุด
st.markdown("""
    <hr style='margin-top: 3rem;'>
    <div style='text-align: center; color: gray;'>
        Provide ระบบสำหรับ วิลล่า มาร์เก็ตเจพี โดยยูนิคอร์น เทค อินทริเกรชั่น
    </div>
""", unsafe_allow_html=True)




