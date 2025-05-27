# app.py
# =============================
import streamlit as st
import os
import sqlite3
import pandas as pd
from urllib.parse import parse_qs, urlparse, unquote, urlencode
from config import CHANNEL_ID, CHANNEL_SECRET, REDIRECT_URI, STATE
from line_api import get_token, get_profile, send_message_to_user
from access_manager import (
    #read_access_log, write_or_update_user, get_approvers, update_user_status,
    read_access_log_db, write_or_update_user_db, get_approvers_db, update_user_status_db
)

DB_FILE = os.path.join("data", "sqdata.db")
SCHEMA_FILE = os.path.join("data", "schema.sql")


st.set_page_config(page_title="Line Login App", page_icon="✅")
st.markdown("<style>footer {visibility: hidden;}</style>", unsafe_allow_html=True)

st.title("📋 เมนูหลัก")
#st.page_link("pages/Call_Recording_Upload.py", label="🎙️ ระบบ Call Recording Upload")

# ----------------------------
# ✅ อ่าน code จาก query string โดยใช้ st.query_params อย่างเดียว
# ----------------------------
code = ""

if "code" in st.query_params:
    code = st.query_params["code"]
    #st.write("🧾 code:", code)

elif "liff.state" in st.query_params:
    try:
        raw = st.query_params["liff.state"]
        decoded = unquote(raw)
        parsed = parse_qs(urlparse(decoded).query)
        code = parsed.get("code", [""])[0]
        st.write("🧾 code (from liff.state):", code)
    except Exception as e:
        st.error(f"❌ ดึง code จาก liff.state ไม่สำเร็จ: {e}")

# ----------------------------
# ✅ ตรวจสอบและเข้าสู่ระบบ
# ----------------------------
if "user_id" not in st.session_state and code:
    token_data = get_token(code, REDIRECT_URI, CHANNEL_ID, CHANNEL_SECRET)
    access_token = token_data.get("access_token")

    if not access_token:
        st.error("❌ ดึง access_token ไม่สำเร็จ")
    else:
        profile = get_profile(access_token)
        user_id = profile.get("userId", "")
        display_name = profile.get("displayName", "")
        picture_url = profile.get("pictureUrl", "")

        if user_id:
            try:
                users = read_access_log_db()
                user_info = users.get(user_id)

                if user_info is None:
                    # 🔰 ผู้ใช้ใหม่ → เพิ่มด้วย status = PENDING
                    write_or_update_user_db(user_id, display_name, picture_url, status="PENDING")
                    user_status = "PENDING"
                else:
                    # 🟢 ผู้ใช้เดิม → ดึง status เดิม
                    user_status = user_info.get("status")
                    # ✅ อัปเดตชื่อ/รูป (ถ้าเปลี่ยน) โดยไม่แตะ status
                    write_or_update_user_db(user_id, display_name, picture_url, status=user_status)

                st.session_state["user_id"] = user_id
                st.session_state["display_name"] = display_name
                st.session_state["status"] = user_status

                st.success(f"🎉 ยินดีต้อนรับ {display_name} ({user_status})")
            except Exception as e:
                st.error(f"❌ ไม่สามารถบันทึกผู้ใช้: {e}")
        else:
            st.error("❌ ไม่พบ userId จาก profile")


# ----------------------------
# ⚙️ Debug Mode Configuration
# ----------------------------
# DEBUG = TRUE  # 🔁 เปลี่ยนเป็น False ก่อน deploy จริง

# if DEBUG:
    # ตั้งค่า session ผู้ใช้ mock สำหรับการทดสอบ
if "user_id" not in st.session_state:
    st.session_state["user_id"] = "Udebug123456"
    st.session_state["displayName"] = "ทดสอบระบบ TEST"
    st.session_state["pictureUrl"] = "https://i.imgur.com/1Q9Z1Zm.png"
    st.session_state["status"] = "APPROVED"
    st.info("🔧 Loaded mock user session for debugging.")

# ----------------------------
# Sidebar Navigation (Dynamic)
# ----------------------------

st.sidebar.title("📋 เมนูหลัก")

# Default: สำหรับคนที่ยังไม่ login
base_menu = [
    "🔐 เข้าสู่ระบบ LINE (ตรวจสอบสิทธิ์)",
    "📌 คุณสมบัติของโปรแกรม",
    "📖 วิธีใช้งานโปรแกรม",
    "🧩 การปรับแต่ง LINE Developers"
]

# เมนูเพิ่มเติมสำหรับผู้ login แล้ว
private_menu = [
    "🖥 หน้าต่างทำงาน",
    "🧾 ตรวจสอบรายชื่อผู้ใช้งาน",
    "📄 ขอดู access_log ไฟล์"
]

# รวมเมนูตามสิทธิ์
if "user_id" in st.session_state and st.session_state.get("status") == "APPROVED":
    menu_options = private_menu + base_menu
else:
    menu_options = base_menu

# ✅ ผูกเมนูเข้ากับ session_state
default_index = menu_options.index(st.session_state["menu"]) if "menu" in st.session_state else 0
st.sidebar.radio("เลือกเมนู", options=menu_options, index=default_index, key="menu")
menu = st.session_state["menu"]

# ----------------------------
# เมนู: หน้าต่างทำงาน
# ----------------------------
if menu == "🖥 หน้าต่างทำงาน":
    st.title("🔐 ระบบเข้าสู่ระบบด้วย LINE")
    st.page_link("pages/Call_Recording_Upload.py", label="🎙️ ระบบ Call Recording Upload")
    st.page_link("pages/Chat_with_AI.py", label="🤖 หน้าต่าง Chat with AI")

# ----------------------------
# เมนู: ตรวจสอบรายชื่อผู้ใช้งาน
# ----------------------------
elif menu == "🧾 ตรวจสอบรายชื่อผู้ใช้งาน":
    st.header("📄 รายชื่อผู้ใช้งานทั้งหมด")
    
    df = read_access_log_db()
    df = df.rename(columns={
        "Display Name": "displayName",
        "Picture URL": "pictureUrl",
        "Status": "status",
        "Last Updated": "updated_at"
    })
    users = df.set_index("User ID").to_dict(orient="index")
    current_user_id = st.session_state.get("user_id", "")
    current_user = users.get(current_user_id, {})
    approvers = get_approvers_db()

    # # -----------------------
    # # DEBUG: ตั้งค่า session ผู้ใช้ทดสอบ
    # # -----------------------
    # if "user_id" not in st.session_state:
    #     st.session_state["user_id"] = "Udebug123456"
    #     st.session_state["displayName"] = "ทดสอบระบบ TEST"
    #     st.session_state["pictureUrl"] = "https://i.imgur.com/1Q9Z1Zm.png"
    #     st.session_state["status"] = "APPROVED"
    #     st.info("🔧 Loaded mock user session for debugging.")

    # ✅ แสดงข้อมูลของคุณ
    st.subheader("🧑‍💼 ข้อมูลของคุณ")
    profile1, profile2, profile3 = st.columns([1, 4, 2])
    with profile1:
        url = current_user.get("pictureUrl", "")
        if url:
            st.image(url, width=80)
        else:
            st.warning("ไม่มีรูปโปรไฟล์")
    with profile2:
        st.markdown(f"""
            **{current_user.get('displayName', 'ไม่ทราบชื่อ')}**  
            🆔 `{current_user_id}`
        """)
    with profile3:
        status = current_user.get("status", "PENDING")
        status_icon = "🟢" if status == "APPROVED" else "🟡" if status == "PENDING" else "🔴"
        st.markdown(f"**สถานะ:** {status_icon} `{status}`")

    if current_user_id in approvers:
        st.success("✅ คุณมีสิทธิ์อนุมัติผู้ใช้งานคนอื่น")
    

        # ✅ แสดงรายชื่อผู้รอการอนุมัติ
        st.markdown("---")
        st.subheader("🧾 ผู้รอการอนุมัติ")

        for uid, info in users.items():
            if info.get("status") == "PENDING" and uid != current_user_id:
                pend1, pend2, pend3 = st.columns([1, 4, 2])
                with pend1:
                    url = info.get("pictureUrl", "")
                    if url:
                        st.image(url, width=60)
                    else:
                        st.warning("ไม่มีรูปโปรไฟล์")
                with pend2:
                    st.markdown(f"**{info.get('displayName')}**  \n🆔 `{uid}`  \n📌 สถานะ: 🟡 `PENDING`")
                with pend3:
                    if st.button("✅ อนุมัติ", key=f"approve_pending_{uid}"):
                        update_user_status_db(uid, "APPROVED")
                        send_message_to_user(uid, "✅ คุณได้รับอนุญาตให้เข้าใช้งาน", "<REPLACE_WITH_TOKEN>")
                        st.rerun()
                    if st.button("🚫 ปฏิเสธ", key=f"deny_pending_{uid}"):
                        update_user_status_db(uid, "DENIED")
                        send_message_to_user(uid, "❌ คุณไม่ได้รับสิทธิ์เข้าใช้งาน", "<REPLACE_WITH_TOKEN>")
                        st.rerun()

    # ✅ แสดงผู้ใช้งานทั้งหมด
    st.markdown("---")
    st.subheader("📋 รายชื่อผู้ใช้งานทั้งหมด")

    status_emoji = {
        "APPROVED": "🟢",
        "PENDING": "🟡",
        "DENIED": "🔴"
    }

    for uid, info in users.items():
        display_name = info.get("displayName", "ไม่ทราบชื่อ")
        status = info.get("status", "PENDING")
        emoji = status_emoji.get(status, "⚪")

        allusers1, allusers2, allusers3, = st.columns([1, 7, 2])
        with allusers1:
            url = info.get("pictureUrl", "")
            if url:
                st.image(url, width=80)
            else:
                st.warning("ไม่มีรูปโปรไฟล์")
        with allusers2:
            st.markdown(f"""
                **{display_name}**  
                🆔 `{uid}`
            """)
        with allusers3:
            if status != "APPROVED" and current_user_id in approvers:
                if st.button("✅ อนุมัติ", key=f"approve_all_{uid}"):
                    update_user_status_db(uid, "APPROVED")
                    st.rerun()
            if status != "DENIED" and current_user_id in approvers:
                if st.button("🚫 ปฏิเสธ", key=f"deny_all_{uid}"):
                    update_user_status_db(uid, "DENIED")
                    st.rerun()
            

# ----------------------------
# เมนู: 📄 ขอดู access_log ไฟล์
# ----------------------------
elif menu == "📄 ขอดู access_log ไฟล์":
    st.title("📄 ข้อมูลผู้ใช้งานจากฐานข้อมูล (access_login)")
    try:
        df = read_access_log_db()
        if df.empty:
            st.info("🔍 ไม่พบข้อมูลผู้ใช้งานในฐานข้อมูล")
        else:
            st.dataframe(df, use_container_width=True)
    except Exception as e:
        st.error(f"❌ ไม่สามารถดึงข้อมูลจากฐานข้อมูลได้: {e}")

    st.title("📄 ขอดู access_log.txt (จากไฟล์)")
    try:
        with open("access_log.txt", "r", encoding="utf-8") as f:
            content = f.read()
        st.text_area("📄 เนื้อหา access_log.txt", value=content, height=300)
    except Exception as e:
        st.error(f"❌ ไม่สามารถเปิด access_log.txt ได้: {e}")

# ----------------------------
# เมนู: 🔐 เข้าสู่ระบบ LINE (ตรวจสอบสิทธิ์)
# ----------------------------
elif menu == "🔐 เข้าสู่ระบบ LINE (ตรวจสอบสิทธิ์)":
    st.title("🔐 ระบบขออนุมัติผ่าน LINE")

    # ใช้ค่าจาก config.py ที่คุณมีอยู่ และ .env
    params = {
        "response_type": "code",
        "client_id": CHANNEL_ID,
        "redirect_uri": REDIRECT_URI,
        "state": STATE,
        "scope": "profile openid",
        "bot_prompt": "aggressive"
    }

    auth_url = f"https://access.line.me/oauth2/v2.1/authorize?{urlencode(params)}"

    # ใช้ปุ่มแบบปลอดภัยของ Streamlit
    st.link_button("🔗 เข้าสู่ระบบด้วย LINE", auth_url)

# -------------------------
# เมนู: คุณสมบัติของโปรแกรม
# -------------------------
elif menu == "📌 คุณสมบัติของโปรแกรม":
    st.title("📌 คุณสมบัติของโปรแกรม")
    st.markdown("""
    ระบบนี้ออกแบบมาเพื่อให้ผู้ใช้งานสามารถยืนยันตัวตนผ่าน LINE ได้อย่างปลอดภัย และสามารถขยายต่อยอดการทำงานร่วมกับ LIFF หรือ Web App อื่น ๆ ได้ง่าย
    รองรับทั้งการตรวจสอบสิทธิ์และการส่งข้อความหา LINE User แบบอัตโนมัติ

    ### 🧱 โครงสร้างไฟล์ของระบบ
    ```plaintext
    line_login_app/
    ├── app.py                  # 🎯 ส่วนติดต่อผู้ใช้งานด้วย Streamlit
    ├── line_api.py             # 📡 รวมฟังก์ชัน backend สำหรับ LINE API (login, push msg)
    ├── config.py               # ⚙️ ค่าคงที่ เช่น Channel ID, Secret, Callback URL
    ├── requirements.txt        # 📦 รายชื่อไลบรารีที่จำเป็นต้องติดตั้ง
    ```

    ### 🛠 ความสามารถหลัก
    - ✅ ตรวจสอบตัวตนผ่าน LINE OAuth2 ได้ทันที
    - ✅ ดึงข้อมูลโปรไฟล์ผู้ใช้งาน เช่น ชื่อ รูป UserID
    - ✅ รองรับการนำไปฝังใน LIFF หรือ Web App ได้
    - ✅ ปรับแต่งหน้าต่าง login ได้เองด้วย Streamlit
    - ✅ พร้อมสำหรับนำไปต่อยอดกับระบบภายในองค์กร
    """)

# -------------------------
# เมนู: วิธีใช้งานโปรแกรม
# -------------------------
elif menu == "📖 วิธีใช้งานโปรแกรม":
    st.title("📖 วิธีใช้งานโปรแกรม")
    st.markdown("""
    เอกสารฉบับนี้จัดทำขึ้นเพื่อแนะนำทั้ง **ผู้ใช้งานทั่วไป** และ **นักพัฒนา (Dev)**
    ให้สามารถติดตั้ง ใช้งาน และปรับแต่งระบบ Login ด้วย LINE ได้อย่างถูกต้อง

    ### ⚙️ สำหรับนักพัฒนา (Dev)
    หากต้องการปรับเปลี่ยนค่าการเชื่อมต่อ LINE (เช่นเปลี่ยน Channel ใหม่ หรือใช้ในโปรเจกต์อื่น):

    🔐 ให้ไปแก้ไขไฟล์ `config.py` ตามนี้:

    ```python
    CHANNEL_ID = "YOUR_LINE_CHANNEL_ID"
    CHANNEL_SECRET = "YOUR_LINE_CHANNEL_SECRET"
    REDIRECT_URI = "YOUR_CALLBACK_URL"
    ```

    - `CHANNEL_ID` และ `CHANNEL_SECRET`: ต้องมาจาก LINE Developers Console ในหัวข้อ **LINE Login**
    - `REDIRECT_URI`: ต้อง **ตรงเป๊ะ** กับที่ลงทะเบียนไว้ใน Console เช่น `https://liff.line.me/xxxx`
    - แนะนำให้ใช้ไฟล์ `.env` สำหรับ production เพื่อไม่ให้ข้อมูลหลุด

    ---

    ### 🧾 ขั้นตอนการติดตั้งระบบ (Installation Guide)

    1. **ติดตั้ง Python**
       ดาวน์โหลดได้ที่ [python.org](https://www.python.org/downloads/)
       ➤ แนะนำใช้ **Python 3.10 ขึ้นไป**

    2. **โคลนหรือดาวน์โหลดโปรเจกต์นี้**
       ```bash
       git clone https://github.com/your-org/line-login-app.git
       cd line-login-app
       ```

    3. **ติดตั้งไลบรารีที่จำเป็น**
       ใช้คำสั่ง:
       ```bash
       pip install -r requirements.txt
       ```

    4. **เรียกใช้งานโปรแกรมด้วย Streamlit**
       ```bash
       streamlit run app.py
       ```

    ---

    ### 🪜 วิธีใช้งานระบบ (User Guide)

    1. เปิดหน้าเว็บและไปยังเมนู **🖥 หน้าต่างทำงาน**
    2. กดปุ่ม **🔗 เข้าสู่ระบบด้วย LINE**
    3. ระบบจะพาไปที่หน้าล็อกอิน LINE (ผ่าน LIFF)
    4. เมื่อยืนยันสำเร็จ จะ redirect กลับและแสดงข้อมูลโปรไฟล์
    5. สามารถใช้ข้อมูล User ID สำหรับระบบอื่น เช่น whitelist หรือส่งข้อความ

    ---

    ✅ หากต้องการนำไปใช้งานร่วมกับระบบองค์กร สามารถฝังภายใน LIFF หรือระบบภายในได้ทันที
    """)

# -------------------------
# เมนู: การปรับแต่ง LINE Developers
# -------------------------
elif menu == "🧩 การปรับแต่ง LINE Developers":
    st.title("🧩 การปรับแต่งใน LINE Developers Console")
    st.markdown("""
    เพื่อให้ระบบสามารถเชื่อมต่อกับ LINE ได้อย่างถูกต้อง จำเป็นต้องตั้งค่าผ่าน [LINE Developers Console](https://developers.line.biz/console/channel/)

    ### 1️⃣ แท็บ Basic settings
    ไปที่เมนู **Basic settings** เพื่อคัดลอกค่าต่อไปนี้:

    - **Channel ID** – ตัวเลขที่ใช้เชื่อมต่อระบบ (ตัวอย่าง: `1660782349`)
    - **Channel secret** – รหัสลับที่ใช้ดึง access token

    > 📝 นำค่านี้มาใส่ในไฟล์ `config.py` หรือ `.env` ตามที่ระบบเรียกใช้งาน

    ---

    ### 2️⃣ แท็บ LINE Login
    ตั้งค่า **Callback URL (Redirect URI)** เพื่อให้ระบบสามารถรับ code กลับมาหลังจาก login สำเร็จ

    - ไปที่หัวข้อ `Callback URL`
    - เพิ่ม URL เช่น:
      ```
      https://liff.line.me/1660782349-xxxxxxxx
      ```
    - ต้อง **ตรงเป๊ะ 100%** กับที่ใช้ในระบบ มิฉะนั้นจะเจอ error `400 Bad Request`

    ---

    ### 3️⃣ แท็บ LIFF
    หากต้องการฝัง Web App ของคุณลงใน LINE:

    - ไปที่แท็บ **LIFF**
    - กด `Add` เพื่อสร้าง LIFF URL ใหม่
    - ระบุ:
      - `Endpoint URL` เช่น `https://your-web-app.com`
      - `Size`: `Compact` / `Tall` / `Full`
    - เมื่อสร้างเสร็จ ระบบจะสร้าง LIFF URL ให้คุณ เช่น:
      ```
      https://liff.line.me/1660782349-8yPr6Q4y
      ```

    > 📌 นำ LIFF URL ไปใช้เป็น `redirect_uri` ในระบบ login ได้ทันที

    ---

    ✅ เมื่อกำหนดค่าทั้ง 3 ส่วนเรียบร้อยแล้ว ระบบจะสามารถเชื่อมต่อและแสดงผลโปรไฟล์ผู้ใช้งานได้อย่างสมบูรณ์
    """)

# Footer ด้านล่างสุด
st.markdown("""
    <hr style='margin-top: 3rem;'>
    <div style='text-align: center; color: #888; font-size: 0.9em;'>
        Provide ระบบสำหรับ วิลล่า มาร์เก็ตเจพี | โดยยูนิคอร์น เทค อินทริเกรชั่น
    </div>
""", unsafe_allow_html=True)