# ไฟล์: main.py
# =============================
import streamlit as st
import urllib.parse
import access_manager
from config import CHANNEL_ID, REDIRECT_URI, STATE, CHANNEL_SECRET
from Database.access_manager import read_access_log_db, write_or_update_user_db
from line_api import get_token, get_profile
import webbrowser

st.set_page_config(page_title="Villa Intelligence", layout="wide")

# โหลดข้อมูลผู้ใช้งานที่อนุมัติแล้ว
approved_users = read_access_log_db()

# จัดการ Session State
if "user_id" not in st.session_state:
    st.session_state.user_id = None
if "is_approved" not in st.session_state:
    st.session_state.is_approved = False
if "display_name" not in st.session_state:
    st.session_state.display_name = ""

# ---------------------
# Sidebar Menu
# ---------------------
st.sidebar.title("📋 เมนูหลัก")
menu = st.sidebar.radio(
    "เลือกเมนู",
    [
        "🔐 เข้าสู่ระบบ LINE (ตรวจสอบสิทธิ์)",
        "🖥 หน้าต่างเลือก  APP",
        "📌 คุณสมบัติของโปรแกรม",
        "📖 วิธีใช้งานโปรแกรม",
        "🧩 การปรับแต่ง LINE Developers",
        "🧾 ตรวจสอบรายชื่อผู้ใช้งาน"
    ]
)

# ---------------------
# เมนู: 🔐 เข้าสู่ระบบ
# ---------------------
if menu == "🔐 เข้าสู่ระบบ LINE (ตรวจสอบสิทธิ์)":
    st.subheader("🔐 เข้าสู่ระบบผ่าน LINE")
    line_login_url = (
        f"https://access.line.me/oauth2/v2.1/authorize?response_type=code"
        f"&client_id={CHANNEL_ID}&redirect_uri={urllib.parse.quote(REDIRECT_URI)}"
        f"&state={STATE}&scope=profile%20openid"
    )
    st.markdown(f"[🔗 คลิกที่นี่เพื่อเข้าสู่ระบบด้วย LINE]({line_login_url})")

    # หลัง redirect จะมี code ใน URL เช่น ?code=XXX&state=YYY
    query_params = st.experimental_get_query_params()
    if "code" in query_params:
        code = query_params["code"][0]
        token_data = get_token(code, REDIRECT_URI, CHANNEL_ID, CHANNEL_SECRET)
        profile = get_profile(token_data["access_token"])

        # บันทึกผู้ใช้ใหม่ หรืออัปเดต
        write_or_update_user_db(
            user_id=profile["userId"],
            display_name=profile["displayName"],
            picture_url=profile["pictureUrl"]
        )

        st.session_state.user_id = profile["userId"]
        st.session_state.display_name = profile["displayName"]

        # ตรวจสอบสถานะการอนุมัติ
        users = read_access_log_db()
        if profile["userId"] in users and users[profile["userId"]]["status"] == "APPROVED":
            st.session_state.is_approved = True
            st.success(f"✅ ยินดีต้อนรับ {profile['displayName']} (ได้รับอนุมัติแล้ว)")
        else:
            st.warning(f"⏳ รอการอนุมัติจากผู้ดูแลระบบ ({profile['displayName']})")

# ---------------------
# เมนู: 🖥 หน้าต่างเลือก APP
# ---------------------
elif menu == "🖥 หน้าต่างเลือก  APP":
    if not st.session_state.is_approved:
        st.error("❌ คุณยังไม่ได้รับสิทธิ์เข้าใช้งาน กรุณาเข้าสู่ระบบและรอการอนุมัติ")
    else:
        st.success(f"🎉 ยินดีต้อนรับ {st.session_state.display_name}")
        st.subheader("🧠 เลือกโปรแกรมที่ต้องการใช้งาน")
        st.markdown("- 🤖 [เข้าสู่แชทบอท](apps/chatbot/main.py)")
        st.markdown("- 🎧 [ระบบ IVR อัตโนมัติ](apps/ivr/main.py)")
        st.markdown("- 📊 ระบบรายงานอื่นๆ (Coming soon)")

# ---------------------
# เมนู: 📌 คุณสมบัติของโปรแกรม
# ---------------------
elif menu == "📌 คุณสมบัติของโปรแกรม":
    st.subheader("📌 คุณสมบัติหลัก")
    st.markdown("""
    - แชทบอท GPT รองรับคำสั่งภาษาไทย
    - รองรับการ Login ด้วย LINE
    - ระบบอนุมัติผู้ใช้งานก่อนเข้าใช้งาน
    - Modular แยกแต่ละแอปชัดเจน
    """)

# ---------------------
# เมนู: 📖 วิธีใช้งาน
# ---------------------
elif menu == "📖 วิธีใช้งานโปรแกรม":
    st.subheader("📖 วิธีใช้งาน")
    st.markdown("""
    1. คลิกเมนู 'เข้าสู่ระบบ LINE'
    2. หากได้รับการอนุมัติแล้ว จะสามารถเข้าเมนู 'หน้าต่างเลือก APP' ได้
    3. เลือกแอปที่ต้องการใช้งาน
    """)

# ---------------------
# เมนู: 🧩 การปรับแต่ง LINE Developers
# ---------------------
elif menu == "🧩 การปรับแต่ง LINE Developers":
    st.subheader("🧩 การตั้งค่า LINE")
    st.markdown("""
    - ตั้งค่า Callback URL: `https://liff.line.me/your-liff-id`
    - เพิ่ม Scope: `profile openid`
    - ตั้งค่า Client ID / Secret ให้ตรงกับ `config.py`
    """)

# ---------------------
# เมนู: 🧾 ตรวจสอบรายชื่อผู้ใช้งาน
# ---------------------
elif menu == "🧾 ตรวจสอบรายชื่อผู้ใช้งาน":
    st.subheader("🧾 รายชื่อผู้ใช้งานระบบ")
    users = read_access_log_db()
    st.table([
        {
            "User ID": uid,
            "ชื่อผู้ใช้": info["displayName"],
            "สถานะ": info["status"]
        } for uid, info in users.items()
    ])
