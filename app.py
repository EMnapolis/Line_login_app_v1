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
    read_access_log_db, write_or_update_user_db, get_approvers_db, get_admin_db
    , update_user_status_db, update_user_role_db, get_user_info_by_id_db
)

DB_FILE = os.path.join("data", "sqdata.db")
SCHEMA_FILE = os.path.join("data", "schema.sql")


st.set_page_config(page_title="Line Login App", page_icon="✅", layout="wide")
st.markdown("<style>footer {visibility: hidden;}</style>", unsafe_allow_html=True)

st.title("📋 เมนูหลัก")

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
                user_info = get_user_info_by_id_db(user_id)
                
                if user_info is None:
                    # 🔰 ผู้ใช้ใหม่ → เพิ่มด้วย status = PENDING
                    write_or_update_user_db(user_id, display_name, picture_url, status="PENDING",role="user")
                    user_status = "PENDING"
                else:
                    # 🟢 ผู้ใช้เดิม → ดึง status เดิม
                    user_status = user_info.get("status")
                    user_role = user_info.get("role")
                    # ✅ อัปเดตชื่อ/รูป (ถ้าเปลี่ยน) โดยไม่แตะ status
                    write_or_update_user_db(user_id, display_name, picture_url, status=user_status,role=user_role)

                st.session_state["user_id"] = user_id
                st.session_state["display_name"] = display_name
                st.session_state["status"] = user_status
                st.session_state["role"] = user_role

                st.success(f"🎉 ยินดีต้อนรับ {display_name} ({user_role}) | ({user_status})")
            except Exception as e:
                st.error(f"❌ ไม่สามารถบันทึกผู้ใช้: {e}")
        else:
            st.error("❌ ไม่พบ userId จาก profile")


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
    "🧾 ตรวจสอบรายชื่อผู้ใช้งาน"
    #"📄 ขอดู access_log ไฟล์"
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
    st.page_link("pages/Google_Transcribe.py", label="🌐 Google Transcribe STT")
# ----------------------------
# เมนู: ตรวจสอบรายชื่อผู้ใช้งาน
# ----------------------------
elif menu == "🧾 ตรวจสอบรายชื่อผู้ใช้งาน":
    st.subheader("📄 รายชื่อผู้ใช้งาน")
    tab_verify, tab_view_all = st.tabs(["🧾 ตรวจสอบรายชื่อผู้ใช้งาน", "📄 ขอดู access_login"])

    with tab_verify:
        df = read_access_log_db()
        df = df.rename(columns={
            "Display Name": "displayName",
            "Picture URL": "pictureUrl",
            "Status": "status",
            "Role": "role",
            "Last Updated": "updated_at"
        })
        users = df.set_index("User ID").to_dict(orient="index")
        current_user_id = st.session_state.get("user_id", "")
        current_user = users.get(current_user_id, {})
        status = current_user.get("status", "PENDING")
        role = current_user.get("role", "user")
        picture_Url = current_user.get("pictureUrl", "")

        can_change_status = role in {"admin", "super admin"}
        can_change_role = role == "super admin"

        # ✅ แสดงข้อมูลของคุณ
        st.subheader("🧑‍💼 ข้อมูลของคุณ")
        profile1, profile2, profile3 = st.columns([1, 4, 2])
        with profile1:
            if picture_Url:
                st.image(picture_Url, width=80)
            else:
                st.warning("ไม่มีรูปโปรไฟล์")
        with profile2:
            st.markdown(f"""
                **{current_user.get('displayName', 'ไม่ทราบชื่อ')}**  
                🆔 `{current_user_id}`   
                **Role:** `{role}`
            """)
        with profile3:
            status_icon = "🟢" if status == "APPROVED" else "🟡" if status == "PENDING" else "🔴"
            st.markdown(f"**สถานะ:** {status_icon} `{status}`")

        if can_change_status:
            st.success("✅ คุณมีสิทธิ์อนุมัติผู้ใช้งานคนอื่น")

            # ✅ แสดงผู้รอการอนุมัติ
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
            user_status = info.get("status", "PENDING")
            user_role = info.get("role", "user")
            emoji = status_emoji.get(user_status, "⚪")

            col1, col2, col3, col4 = st.columns([1, 5, 1, 4])

            with col1:
                url = info.get("pictureUrl", "")
                if url:
                    st.image(url, width=60)
                else:
                    st.warning("no image")

            with col2:
                st.markdown(f"""
                    **{display_name}**
                    🆔 `{uid}`  
                    📌 สถานะ: {emoji} `{user_status}`  
                    🧑‍💼 Role: `{user_role}`
                """)

            with col3:
                if can_change_status and uid != current_user_id:
                    st.markdown("""
                    <div style="display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100%;">
                        <span style="font-size: 14px; margin-bottom: 8px;">เปลี่ยน Status</span>
                    </div>
                    """, unsafe_allow_html=True)
                    if user_status != "APPROVED":
                        if st.button("✅", key=f"approve_all_{uid}", help="อนุมัติผู้ใช้งาน"):
                            update_user_status_db(uid, "APPROVED")
                            st.rerun()
                    if user_status != "DENIED":
                        if st.button("🚫", key=f"deny_all_{uid}", help="ปฏิเสธการเข้าใช้งาน"):
                            update_user_status_db(uid, "DENIED")
                            st.rerun()

            with col4:
                if can_change_role and uid != current_user_id:
                    setrole1, setrole2 = st.columns([2, 1])
                    with setrole1:
                        new_role = st.selectbox(
                            label="เลือก Role",
                            options=["user", "admin", "super admin"],
                            index=["user", "admin", "super admin"].index(user_role),
                            key=f"role_select_{uid}"
                        )
                    with setrole2:
                        st.markdown("""
                            <div style="display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100%;">
                                <span style="font-size: 14px; margin-bottom: 8px;">เปลี่ยน Role</span>
                            </div>
                            """, unsafe_allow_html=True)
                        if st.button("💼 อัปเดต", key=f"update_role_{uid}", help="อัปเดตสิทธิ์บทบาทของผู้ใช้งาน"):
                            update_user_role_db(uid, new_role)
                            st.success(f"✅ เปลี่ยน role ของ `{uid}` เป็น `{new_role}` แล้ว")
                            st.rerun()

            
    with tab_view_all:
    # ----------------------------
    # เมนู: 📄 ขอดู access_log ไฟล์
    # ----------------------------
    # elif menu == "📄 ขอดู access_log ไฟล์":
        st.subheader("📄 ข้อมูลผู้ใช้งานจากฐานข้อมูล (access_login)")
        try:
            df = read_access_log_db()
            if df.empty:
                st.info("🔍 ไม่พบข้อมูลผู้ใช้งานในฐานข้อมูล")
            else:
                st.dataframe(df, use_container_width=True)
        except Exception as e:
            st.error(f"❌ ไม่สามารถดึงข้อมูลจากฐานข้อมูลได้: {e}")


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
    รองรับทั้งการตรวจสอบสิทธิ์ผู้ใช้งาน และการส่งข้อความแบบอัตโนมัติผ่าน LINE Messaging API

    ---

    ### 🧱 โครงสร้างไฟล์ของระบบ

    ```plaintext
    line_login_app_v1/
    ├── app.py                  # 🎯 ส่วนหลักของโปรแกรม (Streamlit UI)
    ├── config.py               # ⚙️ ค่าคงที่ เช่น Channel ID, Secret, Redirect URI
    ├── line_api.py             # 📡 จัดการ LINE API (login, push, profile)
    ├── access_manager.py       # 🔐 จัดการสิทธิ์ผู้ใช้และสถานะ (PENDING/APPROVED)
    ├── call_upload_utils.py    # 🎙️ ฟังก์ชันช่วยในการจัดการไฟล์เสียง
    ├── utility.py              # 🧰 ฟังก์ชันช่วยทั่วไป เช่น token, session, ส่วนใหญ่ ใช้กับ Chat_with_AI
    ├── requirements.txt        # 📦 รายชื่อไลบรารีที่จำเป็นต้องติดตั้ง
    ├── .env                    # 🔒 ตัวแปรความลับ (ใช้ local เท่านั้น)
    ├── .gitignore              # 🚫 กำหนดไฟล์ที่ไม่ต้อง push ขึ้น GitHub

    ├── data/
    │   ├── schema.sql          # 🧱 โครงสร้างตาราง SQLite เช่น access_login, sent_records
    │   └── sqdata.db           # 🗃️ ฐานข้อมูล SQLite ที่ใช้เก็บข้อมูลทั้งหมด

    ├── pages/
    │   ├── Call_Recording_Upload.py  # 🎧 หน้าสำหรับอัปโหลดและส่งไฟล์เสียงเข้า ChatCenter
    │   └── Chat_with_AI.py           # 🤖 หน้าสำหรับสนทนากับ AI ด้วย OpenAI API
    ```

    ---

    ### 🛠 ความสามารถหลักของระบบ

    - ✅ ตรวจสอบตัวตนผ่าน LINE OAuth2 (login + profile)
    - ✅ ดึงชื่อผู้ใช้ รูปภาพ และ userId จาก LINE ได้
    - ✅ จัดการสิทธิ์การเข้าถึงระบบ (PENDING, DENIED, APPROVED)
    - ✅ ส่งข้อความไปยัง LINE User ด้วย Chat Token หรือ Push API
    - ✅ ใช้งานกับ LIFF หรือฝังใน Web App ได้ง่าย
    - ✅ ออกแบบด้วย Streamlit ที่ปรับ UI ได้ตามต้องการ
    - ✅ เก็บข้อมูลผู้ใช้งานและ log ต่าง ๆ ลง SQLite
    - ✅ แยกการเขียนโค้ดแต่ละส่วนตามหน้าที่ (maintain ได้ดี)
    - ✅ พร้อมต่อยอดการใช้งานในองค์กร เช่น CRM, Helpdesk, AI ChatBot
    """)

    st.success("💡 ระบบนี้พร้อมใช้งาน และต่อยอดในระดับ Production ได้ทันที!")


# -------------------------
# เมนู: วิธีใช้งานโปรแกรม
# -------------------------
elif menu == "📖 วิธีใช้งานโปรแกรม":
    st.title("📖 วิธีใช้งานโปรแกรม")

    st.markdown("""
    เอกสารฉบับนี้จัดทำขึ้นเพื่อแนะนำทั้ง **ผู้ใช้งานทั่วไป** และ **นักพัฒนา (Dev)**  
    ให้สามารถติดตั้ง ใช้งาน และปรับแต่งระบบ Login ด้วย LINE ได้อย่างถูกต้อง และปลอดภัย

    ---

    ### ⚙️ สำหรับนักพัฒนา (Developer Guide)

    หากคุณต้องการปรับเปลี่ยนการเชื่อมต่อกับ LINE Platform:

    - ให้ไปแก้ไขไฟล์ `.env` ภายในโฟลเดอร์หลักของโปรเจกต์
    - ยกตัวอย่างค่าที่ใช้:

    ```dotenv
    CHANNEL_ID="YOUR_LINE_CHANNEL_ID"
    CHANNEL_SECRET="YOUR_LINE_CHANNEL_SECRET"
    REDIRECT_URI="YOUR_CALLBACK_URL"
    OPENAI_API_KEY="YOUR_OPENAI_KEY"
    CHAT_TOKEN="YOUR_CHAT_TOKEN"
    ```

    - `CHANNEL_ID`, `CHANNEL_SECRET`: ได้จาก [LINE Developers Console](https://developers.line.biz/)
    - `REDIRECT_URI`: ต้องตรงกับ URI ที่ลงทะเบียนไว้ใน LINE Console
    - สำหรับการ deploy บน **Streamlit Cloud** ให้ใส่ค่าพวกนี้ใน **Secrets** แทน `.env`

    ---

    ### 🧾 ขั้นตอนการติดตั้งระบบ (Installation Guide)

    1. **ติดตั้ง Python**
        - ดาวน์โหลดได้ที่ [python.org](https://www.python.org/downloads/)
        - ✅ แนะนำ Python 3.10 ขึ้นไป

    2. **โคลนหรือดาวน์โหลดโปรเจกต์จาก GitHub**
        ```bash
        git clone https://github.com/your-org/line-login-app.git
        cd line-login-app
        ```

    3. **ติดตั้งไลบรารีที่จำเป็น**
        ```bash
        pip install -r requirements.txt
        ```

    4. **เริ่มต้นระบบด้วย Streamlit**
        ```bash
        streamlit run app.py
        ```

    ---

    ### 🪜 วิธีใช้งานระบบ (User Guide)

    1. ไปที่เมนู **🖥 หน้าต่างทำงาน**
    2. กดปุ่ม **🔗 เข้าสู่ระบบด้วย LINE**
    3. ระบบจะพาไปหน้า LINE Login (OAuth)
    4. เมื่อล็อกอินสำเร็จ ระบบจะแสดงข้อมูลโปรไฟล์ของคุณ
    5. หากคุณมีสถานะเป็น `APPROVED` → คุณสามารถ:
        - เข้าเมนู **🧾 ตรวจสอบรายชื่อผู้ใช้งาน** เพื่ออนุมัติผู้ใช้คนอื่น
        - ใช้งานเมนูต่าง ๆ เช่น **Call Recording Upload**, **Chat with AI**
    6. หากสถานะคุณคือ `PENDING` → กรุณารอให้ admin ทำการอนุมัติ

    ---

    ✅ ระบบนี้สามารถฝังใน **LIFF**, **Web App**, หรือเชื่อมต่อระบบองค์กรได้ทันที  
    🚀 พร้อมสำหรับการใช้งานจริงและการขยายระบบในอนาคต
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

    > 📝 นำค่านี้มาใส่ในไฟล์ `.env` ตามที่ระบบเรียกใช้งาน

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