import google.generativeai as genai
import streamlit as st
import pandas as pd
import sqlite3
import sys 
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config import DATABASE_NAME, DATABASE_FOLDER, PROMPT_FOLDER

DATABASE_PATH = os.path.join(DATABASE_FOLDER, DATABASE_NAME)

# โหลดโมเดล Gemini
if "model" not in st.session_state:
    genai.configure(api_key='AIzaSyBjtH9aXxJVdV0wy_2La3TjPiaJ1EAMqh0')
    model = genai.GenerativeModel('gemini-2.0-flash-lite')
    st.session_state.model = model
model = st.session_state.model

if "history" not in st.session_state:
    st.session_state.history = []

# ************************************************ Backend การทำงานของหน้าเข้าสู่ระบบ ************************************************
def check_user_login(username, password):
    try:
        # เชื่อมต่อฐานข้อมูล
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()

        # ค้นหาผู้ใช้
        cursor.execute("SELECT password FROM users WHERE username = ?", (username,))
        row = cursor.fetchone()
        conn.close()

        # ตรวจสอบว่ามีผู้ใช้นี้หรือไม่
        if row:
            stored_password = row[0]
            return stored_password == password
        else:
            return False

    except sqlite3.Error as e:
        print(f"เกิดข้อผิดพลาดกับฐานข้อมูล: {e}")
        return False


# ************************************************ Backend การทำงานของหน้า LLM ************************************************
def load_history(username, header):
    """โหลดประวัติแชทของ user ในหัวเรื่อง (header) นั้น ๆ"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT prompt, response FROM history
        WHERE username = ? AND header = ?
        ORDER BY id ASC
    """, (username, header))
    rows = cursor.fetchall()
    conn.close()

    history_text = ""
    for prompt, response in rows:
        history_text += f"User: {prompt}\nBot: {response}\n"
    return history_text


def load_history_rows(username, header, source="text"):
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    if source == "text":
        cursor.execute("""
            SELECT prompt, response FROM history
            WHERE username = ? AND header = ?
            ORDER BY timestamp ASC
        """, (username, header))
    else:
        cursor.execute("""
            SELECT prompt, response FROM history_csv
            WHERE username = ? AND header = ?
            ORDER BY timestamp ASC
        """, (username, header))
    rows = cursor.fetchall()
    conn.close()
    return rows


def save_history(username, header, prompt, response, source="text"):
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO history (username, header, prompt, response, source)
            VALUES (?, ?, ?, ?, ?)
        """, (username, header, prompt, response, source))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error saving history: {e}")
        return False


def save_history_csv(username, header, prompt, response, file = None, source="csv"):
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO history_csv (username, header, prompt, response, filedata, source) VALUES (?, ?, ?, ?, ?, ?)
        ''', (username, header, prompt, response, file, source))

        conn.commit()
        conn.close()
        return True
    
    except Exception as e:
        print(f"Error saving history: {e}")
        return False


def generate_answer(username, header, question):
    try:
        # เรียกโมเดล
        response = model.generate_content(question)
        answer = response.text.strip()
        
        if check_comparison_header("history", username, header):
            answer, header = generate_answer_from_memory(username, header, question)

        # บันทึกประวัติ (แม้ไม่มี history ก่อนหน้า)
        save_history(username, header, question, answer)

        return answer, header  # ส่งกลับหัวข้อที่สร้างใหม่นี้ด้วย

    except Exception as e:
        return f"❌ เกิดข้อผิดพลาด: {str(e)}", None


def generate_answer_csv_from_memory(username, header, question, source = 'csv', max_history=10):
    if source == "csv":
        # โหลดประวัติและไฟล์ CSV จากตาราง history_csv
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()

        # ดึง prompt, response, filedata ทั้งหมด
        cursor.execute('''
            SELECT prompt, response, filedata
            FROM history_csv
            WHERE username = ? AND header = ?
            ORDER BY ROWID ASC
        ''', (username, header))
        rows = cursor.fetchall()

        if not rows:
            return "ไม่พบประวัติการสนทนาในหัวข้อนี้", header

        # เช็กว่า filedata ยังมีไหม
        filedata = rows[-1][2]
        if not filedata:
            return "ไม่พบไฟล์ CSV ที่เกี่ยวข้องแล้ว ไม่สามารถใช้ข้อมูลจากไฟล์ช่วยตอบได้", header

        # แยก prompt/response และไฟล์ CSV จากเรคคอร์ดสุดท้าย
        history_rows = [(row[0], row[1]) for row in rows]
        filedata = rows[-1][2] if rows else None

        # แปลง filedata เป็น text หรือ dataframe ตาม format ที่ใช้ (สมมติเป็น csv text)
        import io, pandas as pd
        csv_io = io.StringIO(filedata) if filedata else None
        df_csv = pd.read_csv(csv_io) if csv_io else None

        # สร้าง prompt โดยนำข้อมูล history มาใส่ แล้วเสริมด้วยข้อมูลจาก CSV
        prompt = ""
        for p, r in history_rows[-max_history:]:
            prompt += f"User: {p}\nBot: {r}\n"

        # ถ้าอยากเพิ่มข้อมูลจาก CSV เข้า prompt (ปรับตามโจทย์จริง)
        if df_csv is not None:
            prompt += f"\nข้อมูลจากไฟล์ CSV:\n{df_csv.head().to_string(index=False)}\n"

        prompt += f"User: {question}\nBot:"

        response = model.generate_content(prompt)
        answer = response.text.strip()

        # บันทึกประวัติ (CSV) ต่อเนื่อง
        save_history_csv(username, header, question, answer, filedata, source="csv")

        return answer, header


def generate_answer_from_memory(username, header, question, source = 'text', max_history=10):
    try:
        if source == "csv":
            # โหลดประวัติและไฟล์ CSV จากตาราง history_csv
            conn = sqlite3.connect(DATABASE_PATH)
            cursor = conn.cursor()

            # ดึง prompt, response, filedata ทั้งหมด
            cursor.execute('''
                SELECT prompt, response, filedata
                FROM history_csv
                WHERE username = ? AND header = ?
                ORDER BY ROWID ASC
            ''', (username, header))
            rows = cursor.fetchall()

            if not rows:
                return "ไม่พบประวัติการสนทนาในหัวข้อนี้", header

            # เช็กว่า filedata ยังมีไหม
            filedata = rows[-1][2]
            if not filedata:
                return "ไม่พบไฟล์ CSV ที่เกี่ยวข้องแล้ว ไม่สามารถใช้ข้อมูลจากไฟล์ช่วยตอบได้", header

            # แยก prompt/response และไฟล์ CSV จากเรคคอร์ดสุดท้าย
            history_rows = [(row[0], row[1]) for row in rows]
            filedata = rows[-1][2] if rows else None

            # แปลง filedata เป็น text หรือ dataframe ตาม format ที่ใช้ (สมมติเป็น csv text)
            import io, pandas as pd
            csv_io = io.StringIO(filedata) if filedata else None
            df_csv = pd.read_csv(csv_io) if csv_io else None

            # สร้าง prompt โดยนำข้อมูล history มาใส่ แล้วเสริมด้วยข้อมูลจาก CSV
            prompt = ""
            for p, r in history_rows[-max_history:]:
                prompt += f"User: {p}\nBot: {r}\n"

            # ถ้าอยากเพิ่มข้อมูลจาก CSV เข้า prompt (ปรับตามโจทย์จริง)
            if df_csv is not None:
                prompt += f"\nข้อมูลจากไฟล์ CSV:\n{df_csv.head().to_string(index=False)}\n"

            prompt += f"User: {question}\nBot:"

            response = model.generate_content(prompt)
            answer = response.text.strip()

            # บันทึกประวัติ (CSV) ต่อเนื่อง
            save_history_csv(username, header, question, answer, filedata, source="csv")

            return answer, header

        else:
            # source == "text" หรืออื่น ๆ
            history_rows = load_history_rows(username, header, source=source)
            history_rows = history_rows[-max_history:]

            prompt = ""
            for p, r in history_rows:
                prompt += f"User: {p}\nBot: {r}\n"
            prompt += f"User: {question}\nBot:"

            response = model.generate_content(prompt)
            answer = response.text.strip()

            save_history(username, header, question, answer, source=source)

            return answer, header

    except Exception as e:
        print(f"Error in generate_answer_from_memory: {e}")
        return "ขออภัย เกิดข้อผิดพลาดในการประมวลผล", header


    except Exception as e:
        # fallback ถ้ามีปัญหา
        answer, new_header = generate_answer(username, question)  # ตรงนี้คุณส่งผิดเป็น prompt
        save_history(username, new_header, question, answer)

        return answer, new_header  # ✅ return 2 ค่าให้เหมือนกัน

def generate_header_from_text(text):
    prompt = f"ตั้งชื่อหัวข้อสั้น ๆ หัวข้อเดียวแล้วจบสำหรับบทสนทนานี้ พยายามตั้งชื่อหัวข้อให้ใกล้เคียงมากที่สุด: '{text}'"
    response = model.generate_content(prompt)
    header = response.text.strip()

    # ลบ ** ข้างหน้าและข้างหลังถ้ามี
    if header.startswith("**") and header.endswith("**"):
        header = header[2:-2].strip()

    return header

def delete_history(username: str, header: str):
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM history WHERE username = ? AND header = ?", (username, header))
        conn.commit()
        conn.close()
    except Exception as e:
        st.error(f"เกิดข้อผิดพลาดในการลบ: {e}")


def delete_history_csv(username, header):
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        cursor.execute('DELETE FROM history_csv WHERE username = ? AND header = ?', (username, header))
        conn.commit()
        conn.close()
    except Exception as e:
        st.error(f"เกิดข้อผิดพลาดในการลบ: {e}")

# ส่วนของ CSV
# ===== MAIN CSV ANALYSIS FUNCTION =====
def generate_csv(uploaded_file, username, header, prompt):
    if uploaded_file is None:
        return "❌ ไม่พบไฟล์ CSV ที่แนบไว้"

    try:
        # อ่านไฟล์เป็นข้อความ
        file_bytes = uploaded_file.read().decode("utf-8")
    except Exception as e:
        return f"❌ ไม่สามารถอ่านไฟล์ CSV ได้: {e}"

    # 🔮 ส่งข้อความ + ไฟล์เข้าไปใน LLM
    system_message = (
        "คุณคือผู้ช่วยด้านข้อมูล CSV โปรดวิเคราะห์ข้อมูลตามคำถามที่ได้รับ "
        "คุณสามารถเขียนโค้ด Python, สรุปข้อมูล หรือแนะนำการวิเคราะห์จากไฟล์ CSV ด้านล่างได้"
    )
    full_prompt = f"{system_message}\n\n--- ข้อมูล CSV ---\n{file_bytes[:3000]}\n\n--- คำถาม ---\n{prompt}"

    try:
        # 👇 เปลี่ยนให้เข้ากับ LLM ที่คุณใช้ เช่น Gemini / OpenAI
        response = model.generate_content(full_prompt)
        answer = response.text.strip()

        save_history_csv(username, header, prompt, answer, file_bytes)

    except Exception as e:
        return f"❌ เกิดข้อผิดพลาดระหว่างการใช้โมเดล: {e}"

    return answer


def check_comparison_header(table_name, username, header): 
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()

        # เช็กว่าตารางมี row อย่างน้อย 1 แถวไหม
        cursor.execute(f"SELECT EXISTS(SELECT 1 FROM {table_name} LIMIT 1);")
        has_row = cursor.fetchone()[0]

        if not has_row:
            conn.close()
            return False

        if header is not None:
            # ดึง header ที่มีในตารางของ user คนนี้
            cursor.execute(f"SELECT DISTINCT header FROM {table_name} WHERE username = ?", (username,))
            headers_in_db = [row[0] for row in cursor.fetchall()]

            conn.close()
            return header in headers_in_db  # ✅ ตรวจว่ามี header นี้อยู่ในของ user นี้หรือไม่

        conn.close()

    except Exception as e:
        print(f"❌ Error checking table rows or header: {e}")
        return False


    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()

        # เช็กว่าตารางมี row อย่างน้อย 1 แถวไหม
        cursor.execute(f"SELECT EXISTS(SELECT 1 FROM {table_name} LIMIT 1);")
        has_row = cursor.fetchone()[0]

        conn.close()
        return has_row == 1

    except Exception as e:
        print(f"❌ Error checking table rows: {e}")
        return False


def check_header(username):
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    # ดึง header จาก history (chat)
    cursor.execute("""
        SELECT DISTINCT header, 'text' as source
        FROM history
        WHERE username = ?
    """, (username,))
    chat_headers = cursor.fetchall()

    # ดึง header จาก history_csv
    cursor.execute("""
        SELECT DISTINCT header, 'csv' as source
        FROM history_csv
        WHERE username = ?
    """, (username,))
    csv_headers = cursor.fetchall()

    conn.close()

    # รวม 2 ชุดข้อมูล
    combined_headers = chat_headers + csv_headers

    # ถ้าต้องการไม่ให้ซ้ำ ให้กรองด้วย set หรือ dict
    unique = {}
    for h, s in combined_headers:
        unique[(h, s)] = None

    return list(unique.keys())  # [(header, source), ...]


# ************************************************ Backend การทำงานของ add prompt ************************************************
# ✅ BACKEND FUNCTION: ฟังก์ชันสำหรับบันทึก Prompt
def save_prompt_to_file(folder: str, name: str, ext: str, content: str) -> (bool, str):
    
    if (folder is None): 
        folder = PROMPT_FOLDER

    """
    บันทึก prompt ลงไฟล์ในโฟลเดอร์ที่กำหนด
    :return: (status, message)
    """
    os.makedirs(folder, exist_ok=True)
    file_name = f"{name}.{ext}"
    file_path = os.path.join(folder, file_name)

    if os.path.exists(file_path):
        return False, f"⚠️ ไฟล์ `{file_name}` มีอยู่แล้วในโฟลเดอร์ `{folder}` กรุณาเปลี่ยนชื่อไฟล์ใหม่ค่ะ"
    
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)

    return True, f'✅ ไฟล์ถูกบันทึกลงในโฟลเดอร์ `{folder}` เรียบร้อยแล้ว\n\nชื่อไฟล์: `{file_name}`'


# ************************************************ Backend การทำงานของ update prompt ************************************************
# ✅ BACKEND FUNCTION: ฟังก์ชันสำหรับ Update Prompt
def update_prompt_file(file_path: str, new_content: str) -> tuple[bool, str]:
    """
    อัปเดตเนื้อหาในไฟล์ Prompt ที่กำหนด
    return: (status, message)
    """
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(new_content)
        return True, f"✅ บันทึกไฟล์ `{os.path.basename(file_path)}` เรียบร้อยแล้ว"
    except Exception as e:
        return False, f"เกิดข้อผิดพลาดในการบันทึกไฟล์: {e}"


# ************************************************ Backend การทำงานของ delete prompt ************************************************
# ✅ BACKEND FUNCTION: ฟังก์ชันสำหรับ delete Prompt
def delete_prompt_file(file_path: str) -> tuple[bool, str]:
    """
    ลบไฟล์ Prompt ที่ระบุ
    return: (status, message)
    """
    try:
        os.remove(file_path)
        return True, "ลบไฟล์เรียบร้อยแล้ว ✅"
    except Exception as e:
        return False, f"เกิดข้อผิดพลาดในการลบไฟล์: {e}"
    
