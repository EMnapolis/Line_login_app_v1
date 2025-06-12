#pages/Google_Translate.py
import streamlit as st
import os
import io
import base64
from google.cloud import translate
from google.cloud.translate import TranslationServiceClient
from google.oauth2 import service_account
from datetime import datetime

#--------------------
# ประกาศใช้ ฟังก์ชัน
#--------------------
def load_credentials_from_base64():
    key_b64 = os.getenv("GOOGLE_KEY_B64")
    if not key_b64:
        raise ValueError("GOOGLE_KEY_B64 ไม่พบใน environment")
    
    key_json = base64.b64decode(key_b64).decode("utf-8")
    with open("temp_key.json", "w", encoding="utf-8") as f:
        f.write(key_json)

    credentials = service_account.Credentials.from_service_account_file("temp_key.json")
    return credentials

def log_error_to_file(message):
    with open("Error.txt", "a", encoding="utf-8") as error_file:
        error_file.write(f"{datetime.now()}: {message}\n")

def translate_text(text, target_language, source_language=None):
    try:
        credentials = load_credentials_from_base64()
        client = TranslationServiceClient(credentials=credentials)

        project_id = credentials.project_id
        parent = f"projects/{project_id}/locations/global"

        # สร้าง arguments โดยไม่ส่ง source_language หากไม่ระบุ
        request_args = {
            "parent": parent,
            "contents": [text],
            "mime_type": "text/plain",
            "target_language_code": target_language,
        }
        if source_language:
            request_args["source_language_code"] = source_language

        response = client.translate_text(**request_args)
        return response.translations[0].translated_text

    except Exception as e:
        log_error_to_file(f"เกิดข้อผิดพลาดขณะแปลภาษา: {e}")
        return None

#--------------------
# จบการประกาศใช้ ฟังก์ชัน
#--------------------

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

#---------------
# ✅ ตรวจ login และสิทธิ์
if "user_id" not in st.session_state or st.session_state.get("status") != "APPROVED":
    st.error("🚫 กรุณาเข้าสู่ระบบ และรอการอนุมัติ")
    st.stop()

#---------------
# เริ่มต้น Fontend
#---------------
st.set_page_config(page_title="Google Translate", page_icon="🌐", layout="wide")

# Header ด้านบนขวา
st.markdown("""
    <div style='position: absolute; top: 1rem; right: 2rem; font-size: 20px; font-weight: bold;'>
        Google Translate
    </div>
""", unsafe_allow_html=True)

# Sidebar menu
st.page_link("app.py", label="⬅️ กลับหน้าหลัก", icon="🏠")
st.sidebar.title("📋 เมนูหลัก")
menu = st.sidebar.radio("เลือกเมนู", ["🖥 หน้าต่างทำงาน", "📌 คุณสมบัติของโปรแกรม", "📖 วิธีใช้งานโปรแกรม"])


if menu == "🖥 หน้าต่างทำงาน":
    # Main Title
    st.title("🌐 Google Translate API")

    maincol1, maincol2 = st.columns(2) # แบ่งคอลัมน์ให้เป็นแบบคู่

    with maincol1:
        st.subheader("📝 ข้อความต้นฉบับ")
        original_text = st.text_area("กรอกข้อความที่ต้องการแปล", height=200, key="original_text")

        st.markdown("""🌐 เลือกภาษาต้นฉบับ และ ปลายทาง""")
        subcol1, subcol2 = st.columns(2)
        with subcol1:
            source_language_options = [
                ("ตรวจจับอัตโนมัติ", None),
                ("ไทย (th)", "th"),
                ("อังกฤษ (en)", "en"),
                ("จีนกลาง (zh-CN)", "zh-CN"),
                ("ญี่ปุ่น (ja)", "ja"),
                ("เกาหลี (ko)", "ko"),
                ("รัสเซีย (ru)", "ru"),
                # เพิ่มภาษาอื่น ๆ ที่ต้องการ
            ]
            selected_source_lang_display, selected_source_lang_code = st.selectbox(
                "เลือกภาษาต้นฉบับ",
                options=source_language_options,
                index=0,
                format_func=lambda x: x[0],
                key="source_lang_selector"
            )

        with subcol2:
            #st.markdown("""🌐 เลือกภาษาปลายทาง""")
            target_language_options = [
                ("ไทย (th)", "th"),
                ("อังกฤษ (en)", "en"),
                ("จีนกลาง (zh-CN)", "zh-CN"),
                ("ญี่ปุ่น (ja)", "ja"),
                ("เกาหลี (ko)", "ko"),
                ("รัสเซีย (ru)", "ru"),
                # เพิ่มภาษาอื่น ๆ ที่ต้องการ
            ]
            selected_target_lang_display, selected_target_lang_code = st.selectbox(
                "เลือกภาษาปลายทาง",
                options=target_language_options,
                index=0, # Default to English
                format_func=lambda x: x[0],
                key="target_lang_selector"
            )
        
        # ปุ่มแปลภาษา
        translate_button = st.button("🚀 แปลภาษา")

    with maincol2:
        st.subheader("📄 ผลลัพธ์การแปล")
        if translate_button and original_text:
            with st.spinner("⏳ กำลังแปลภาษา..."):
                translated_text = translate_text(original_text, selected_target_lang_code, selected_source_lang_code)
                if translated_text:
                    st.success("✅ แปลภาษาเรียบร้อย")
                    st.text_area("📜 ข้อความที่แปล", translated_text, height=200, key="translated_output")
                    st.download_button("💾 ดาวน์โหลดเป็น .txt", translated_text, file_name="translated_text.txt", mime="text/plain")
                else:
                    st.error("❌ ไม่สามารถแปลภาษาได้ กรุณาตรวจสอบข้อความหรือการตั้งค่า")
        elif translate_button and not original_text:
            st.warning("⚠️ กรุณาป้อนข้อความที่ต้องการแปล")

elif menu == "📌 คุณสมบัติของโปรแกรม":
    st.title("📌 คุณสมบัติของโปรแกรม Google Translate")
    st.markdown("""
    โปรแกรมนี้เป็นส่วนหนึ่งของระบบ Streamlit Cloud ของคุณที่ใช้ Google Cloud Translation API เพื่อการแปลภาษาที่มีประสิทธิภาพ.
    
    * **รองรับหลายภาษา**: สามารถแปลข้อความจากและไปสู่ภาษาต่าง ๆ ที่ Google Translation API รองรับ.
    * **ตรวจจับภาษาต้นฉบับอัตโนมัติ**: หากคุณไม่แน่ใจภาษาต้นฉบับ ระบบสามารถตรวจจับและแปลให้อัตโนมัติ.
    * **ใช้งานง่าย**: อินเทอร์เฟซผู้ใช้ที่เรียบง่ายและใช้งานง่ายสำหรับการป้อนข้อความและการรับผลลัพธ์.
    * **ดาวน์โหลดผลลัพธ์**: สามารถดาวน์โหลดข้อความที่แปลแล้วเป็นไฟล์ `.txt` ได้.
    * **ความปลอดภัย**: ใช้ Google Service Account Credentials ที่เข้ารหัส Base64 (GOOGLE_KEY_B64) เพื่อการยืนยันตัวตนที่ปลอดภัย.
    """)

elif menu == "📖 วิธีใช้งานโปรแกรม":
    st.title("📖 วิธีใช้งานโปรแกรม Google Translate")
    st.markdown("""
    โปรแกรมนี้ออกแบบมาเพื่อให้คุณสามารถแปลข้อความได้อย่างรวดเร็วและง่ายดาย.
    
    ---

    ### 1. การเข้าถึงและล็อกอิน
    * คุณต้องเข้าสู่ระบบและได้รับการอนุมัติสถานะ (`APPROVED`) เพื่อใช้งานโปรแกรม.

    ### 2. หน้าต่างทำงาน (`🖥 หน้าต่างทำงาน`)
    * **กรอกข้อความต้นฉบับ**: ในช่อง `📝 ข้อความต้นฉบับ` ให้คุณพิมพ์หรือวางข้อความที่คุณต้องการแปล.
    * **เลือกภาษาต้นฉบับ**: หากคุณทราบภาษาของข้อความต้นฉบับ ให้เลือกจากช่อง `🌐 เลือกภาษาต้นฉบับ`. หากไม่ทราบหรือไม่แน่ใจ สามารถเลือก `ตรวจจับอัตโนมัติ` เพื่อให้ระบบของ Google ตรวจจับให้เอง.
    * **เลือกภาษาปลายทาง**: เลือกภาษาที่คุณต้องการให้แปลข้อความไปในช่อง `🌐 เลือกภาษาปลายทาง`.
    * **กดปุ่ม "แปลภาษา"**: หลังจากตั้งค่าทั้งหมดแล้ว ให้กดปุ่ม `🚀 แปลภาษา` เพื่อเริ่มกระบวนการ.
    * **ดูผลลัพธ์**: ข้อความที่แปลแล้วจะปรากฏในช่อง `📜 ข้อความที่แปล`.
    * **ดาวน์โหลดผลลัพธ์**: คุณสามารถกดปุ่ม `💾 ดาวน์โหลดเป็น .txt` เพื่อบันทึกข้อความที่แปลแล้วลงในเครื่องคอมพิวเตอร์ของคุณ.

    ---

    ### 3. คุณสมบัติของโปรแกรม (`📌 คุณสมบัติของโปรแกรม`)
    * หน้านี้จะแสดงรายละเอียดเกี่ยวกับคุณสมบัติหลักของโปรแกรม Google Translate.

    ---

    ### 4. วิธีใช้งานโปรแกรม (`📖 วิธีใช้งานโปรแกรม`)
    * หน้านี้เป็นคู่มือการใช้งานที่คุณกำลังอ่านอยู่.

    ---

    **ข้อควรระวัง**:
    * ตรวจสอบให้แน่ใจว่าได้กำหนดค่า `GOOGLE_KEY_B64` ใน Environment Variables ของ Streamlit Cloud อย่างถูกต้อง เพื่อให้โปรแกรมสามารถเชื่อมต่อกับ Google Cloud Translation API ได้.
    * หากเกิดข้อผิดพลาดใดๆ โปรแกรมจะพยายามบันทึกข้อผิดพลาดลงในไฟล์ `Error.txt`.
    """)