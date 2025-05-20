# Call_Recording_Upload/main.py
import streamlit as st
from utils import process_audio

def render_page():
    st.title("🎙️ ระบบ Call Recording Upload")

    # ✅ ตรวจว่า login แล้วหรือยัง
    if "user_id" not in st.session_state:
        st.warning("⚠️ กรุณาเข้าสู่ระบบก่อนใช้งาน")
        st.stop()

    # ✅ ตรวจว่าได้รับสิทธิ์แล้วหรือยัง
    if st.session_state.get("status") != "APPROVED":
        st.error("🚫 คุณยังไม่ได้รับสิทธิ์ใช้งานหน้านี้")
        st.stop()

    # ✅ ส่วนที่แสดง UI จริง
    st.title("ส่วนที่แสดง UI จริง")
