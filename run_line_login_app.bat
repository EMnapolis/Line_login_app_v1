@echo off
:: ไฟล์: run_line_login_app.bat
:: ใช้รันแอป Streamlit ที่ชื่อว่า app.py

:: กำหนด Python PATH ตามที่เครื่องคุณใช้งาน (ปรับตามเครื่องได้)
SET PYTHON_EXEC=python

:: แสดงข้อความเริ่มต้น
echo -------------------------------------
echo LINE Login by Streamlit
echo -------------------------------------

:: รันแอป Streamlit
%PYTHON_EXEC% -m streamlit run app.py

:: รอให้ผู้ใช้กดปิด
pause