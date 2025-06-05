#pages/Google_Transcribe.py
import streamlit as st
import os
import io
import base64
from google.cloud import speech
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
        error_file.write(f"{message}\n")

def transcribe_local_audio(audio_path, language_code="th-TH", model="default"):
    try:
        credentials = load_credentials_from_base64()
        client = speech.SpeechClient(credentials=credentials)

        with open(audio_path, "rb") as f:
            content = f.read()

        audio = speech.RecognitionAudio(content=content)

        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
            language_code=language_code,
            model=model,
            sample_rate_hertz=8000  # fallback default
        )

        response = client.recognize(config=config, audio=audio)

        transcript = "\n".join([result.alternatives[0].transcript for result in response.results])

        # ลบไฟล์หลังใช้
        try:
            delete_temp_audio(audio_path)
        except Exception as e:
            log_error_to_file(f"ไม่สามารถลบไฟล์ชั่วคราว: {e}")

        return transcript

    except Exception as e:
        log_error_to_file(f"เกิดข้อผิดพลาดขณะแปลงเสียง: {e}")
        return None

def save_temp_audio(file, filename):
    try:
        os.makedirs("tmp", exist_ok=True)
        temp_path = os.path.join("tmp", filename)
        with open(temp_path, "wb") as f:
            f.write(file.getbuffer())
        return temp_path
    except Exception as e:
        log_error_to_file(f"ไม่สามารถบันทึกไฟล์ชั่วคราว: {e}")
        return None

def delete_temp_audio(file_path):
    try:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
            return True
        else:
            log_error_to_file(f"ไม่พบไฟล์ที่จะลบ: {file_path}")
            return False
    except Exception as e:
        log_error_to_file(f"เกิดข้อผิดพลาดขณะลบไฟล์ชั่วคราว: {e}")
        return False

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
st.set_page_config(page_title="Google STT", layout="wide")

# Header ด้านบนขวา
st.markdown("""
    <div style='position: absolute; top: 1rem; right: 2rem; font-size: 20px; font-weight: bold;'>
        Google Transcribe STT
    </div>
""", unsafe_allow_html=True)

# Sidebar menu
st.page_link("app.py", label="⬅️ กลับหน้าหลัก", icon="🏠")
st.sidebar.title("📋 เมนูหลัก")
menu = st.sidebar.radio("เลือกเมนู", ["🖥 หน้าต่างทำงาน", "📌 คุณสมบัติของโปรแกรม", "📖 วิธีใช้งานโปรแกรม"])


if menu == "🖥 หน้าต่างทำงาน":
    # Main Title
    st.title("🌐 Google Speech-to-Text")

    # # ---------------------
    # # Step 1: Browse Credential JSON
    # # ---------------------
    # # st.markdown("<small><b>ขยายเพื่อแก้ไข Credential (Google JSON)</b></small>", unsafe_allow_html=True)
    # with st.expander("ขยายเพื่อแก้ไข Credential (Google JSON)", expanded=False):
    #     st.subheader("🔐 เลือกไฟล์ Credential (Google JSON)")
    #     json_file = st.file_uploader("เลือกไฟล์ .json", type="json")

    #     if json_file:
    #         json_path = f"temp_cred.json"
    #         with open(json_path, "wb") as f:
    #             f.write(json_file.getbuffer())
    #         st.success(f"โหลด Credential สำเร็จ: {json_file.name}")

    col1, col2 = st.columns(2)  # แบ่งคอลัมน์ให้เลือกวันที่แบบคู่
    with col1:
        # ---------------------
        # Step 2: เลือกไฟล์เสียง (LOCAL)
        # ---------------------
        st.subheader("🎙️ เลือกไฟล์เสียงจากเครื่องคุณ")
        audio_file = st.file_uploader("เลือกไฟล์เสียง (.wav, .mp3)", type=["wav", "mp3"])

        if audio_file:
            local_audio_path = f"temp_audio_{audio_file.name}"
            with open(local_audio_path, "wb") as f:
                f.write(audio_file.getbuffer())
            #st.info(f"ไฟล์เสียง: {audio_file.name}")
            lang_col, model_col  = st.columns(2)  # แบ่งคอลัมน์ให้เลือก
            with lang_col:
                st.markdown("""🌐 เลือกภาษาสำหรับการถอดเสียง""")
                language_code = st.selectbox(
                    "เลือกภาษา",
                    options=[
                        ("ไทย (th-TH)", "th-TH"),
                        ("อังกฤษ (en-US)", "en-US"),
                        ("จีนกลาง (zh-CN)", "zh-CN"),
                        ("ญี่ปุ่น (ja-JP)", "ja-JP"),
                        ("เกาหลี (ko-KR)", "ko-KR"),
                        ("รัสเซีย (ru-RU)", "ru-RU")
                    ],
                    index=0,  # ค่า default คือ "ไทย"
                    format_func=lambda x: x[0]
                )[1] # <-- ได้เฉพาะ language_code
            with model_col:
                st.markdown("""🌐 เลือก Model""")
                model  = st.selectbox(
                    "เลือก Model",
                    options=[
                        ("model  Long", "latest_long"),
                        ("model  Short", "latest_short"),
                        ("Default - Legacy", "default")
                    ],
                    index=0,  # ค่า default คือ "latest_long"
                    format_func=lambda x: x[0]
                )[1] # <-- ได้เฉพาะ model

            # ปุ่มอยู่ที่ col1
            generate_transcript = st.button("🎙️📝 สร้าง Transcript")
        else:
            generate_transcript = False  # ป้องกัน error หากไฟล์ยังไม่ถูกอัปโหลด
    with col2:
        # ---------------------
        # Step 3: ปุ่มแปลงเสียงเป็นข้อความ
        # ---------------------
        if generate_transcript:
            st.subheader("📄 ผลลัพธ์การถอดเสียง")
            with st.spinner("⏳ กำลังประมวลผล..."):
                try:
                    transcript = transcribe_local_audio(local_audio_path, language_code, model)
                    st.success("✅ ถอดเสียงเรียบร้อย")
                    st.text_area("📜 Transcript", transcript, height=185)
                    st.download_button("💾 ดาวน์โหลดเป็น .txt", transcript, file_name="transcript.txt")
                except Exception as e:
                    st.error(f"เกิดข้อผิดพลาด: {e}")

# -------------------------
# เมนู: คุณสมบัติของโปรแกรม
# -------------------------
elif menu == "📌 คุณสมบัติของโปรแกรม":
    st.title("📌 คุณสมบัติของโปรแกรม")
    st.markdown("""
    - ใช้เทคโนโลยี **Google Cloud Speech-to-Text** ในการถอดเสียงเป็นข้อความ
    - รองรับการอัปโหลดไฟล์เสียง `.wav` และ `.mp3`
    - รองรับ Credential ไฟล์ `.json` จาก Google Cloud
    - แสดงข้อความที่ถอดเสียงได้ทันที พร้อมให้ดาวน์โหลดเป็น `.txt`
    - ใช้งานง่ายผ่านหน้าต่างเว็บด้วย **Streamlit**
    """)

# -------------------------
# เมนู: วิธีใช้งานโปรแกรม
# -------------------------
elif menu == "📖 วิธีใช้งานโปรแกรม":
    st.title("📖 วิธีใช้งานโปรแกรม")
    st.markdown("""
    ### 🧾 ขั้นตอนการติดตั้ง

    1. **ติดตั้ง Python**  
       ดาวน์โหลดจาก [python.org](https://www.python.org/downloads/) (แนะนำ Python 3.10 ขึ้นไป)

    2. **ติดตั้งไลบรารีที่จำเป็น**  
       เปิด Terminal หรือ Command Prompt แล้วรัน:

       ```bash
       pip install streamlit google-cloud-speech
       ```

    3. **เปิดใช้งานโปรแกรม**  

       ```bash
       streamlit run main.py
       ```

    ### 🪜 วิธีใช้งาน

    1. **อัปโหลด Credential (.json)** ที่ได้จาก Google Cloud Console
    2. **เลือกไฟล์เสียง** ที่ต้องการถอดข้อความ (.wav หรือ .mp3)
    3. **เลือกภาษา** ที่ต้องการให้ระบบวิเคราะห์เสียง เช่น ไทย, อังกฤษ, จีน ฯลฯ
    4. **เลือกโมเดลการถอดเสียง** (เช่น `latest_long`, `latest_short`, หรือ `default`) ให้เหมาะกับความยาวของบทสนทนา
    5. กด **ปุ่มถอดเสียง** แล้วรอให้ระบบประมวลผล
    6. ตรวจสอบข้อความที่ได้ และสามารถ **ดาวน์โหลดเป็นไฟล์ .txt** ได้ทันที

    ใช้งานง่ายผ่านหน้าเว็บ ไม่ต้องเขียนโค้ดเอง!
    """)

# Footer ด้านล่างสุด
st.markdown("""
    <hr style='margin-top: 3rem;'>
    <div style='text-align: center; color: gray;'>
        Provide ระบบสำหรับ วิลล่า มาร์เก็ตเจพี โดยยูนิคอร์น เทค อินทริเกรชั่น
    </div>
""", unsafe_allow_html=True)