import os
import sys
import streamlit as st

# เพิ่ม path ให้ import ได้
sys.path.append(os.path.join(os.path.dirname(__file__), "Call_Recording_Upload"))

# เรียกฟังก์ชันแสดงหน้าหลัก
from main import render_page
render_page()
