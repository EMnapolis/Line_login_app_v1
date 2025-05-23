import streamlit as st
import pandas as pd 
import hashlib
import time
import os 

from config import PROMPT_FOLDER

from call_llmPrompt_utils import (
    check_user_login, save_history, save_history_csv, load_history, load_history_rows, delete_history, delete_history_csv,
    generate_answer, generate_header_from_text, generate_answer_from_memory, generate_csv, check_header, delete_history, generate_answer_csv_from_memory, check_comparison_header,
    save_prompt_to_file, update_prompt_file, delete_prompt_file
)

# if "user_id" not in st.session_state or st.session_state.get("status") != "APPROVED":
#     st.error("🚫 กรุณาเข้าสู่ระบบ และรอการอนุมัติ")
#     st.stop()

def set_username(user):
    st.session_state.username = user

# ดึงค่า username
def get_username():
    return st.session_state.get("username", "")


# ส่วนปรับความสวยงามใน steamlit ด้วย css
def beautiful_markdown_st():
    st.markdown("""
    <style>
                    
    /* ปรับช่องว่างด้านล่างของแต่ละ radio button */
    div[role="radiogroup"] > label {
        margin-bottom: 15px;  /* ปรับเลขนี้ตามที่ต้องการ */
    }
                
    </style>
    """, unsafe_allow_html=True)
    
beautiful_markdown_st()

menu_login = "🔐 เข้าสู่ระบบ"
menu_ask = "💬 ถาม AI"
menu_add = "➕ เพิ่ม Prompt"
menu_update = "✏️ แก้ไข Prompt"
menu_delete = "🗑️ ลบ Prompt"

menus = [menu_login, menu_ask, menu_add, menu_update, menu_delete]

# ตั้งค่า default
if "menu_bar" not in st.session_state:
    st.session_state.menu_bar = menu_login

# ถ้ามีคำสั่งสลับเมนู ให้เปลี่ยนค่า session_state.menu_bar ก่อนสร้าง widget
if "switch_to_menu" in st.session_state:
    st.session_state.menu_bar = st.session_state.switch_to_menu
    del st.session_state.switch_to_menu
    st.rerun()  # รีรันหน้าใหม่

# ดึง index ของเมนูเพื่อให้ sidebar radio แสดงผลถูกต้อง
menu_index = menus.index(st.session_state.menu_bar)

# สร้าง sidebar radio พร้อม key menu_bar
menu_bar = st.sidebar.radio("เลือกเมนู", menus, index=menu_index, key="menu_bar")

# แสดงหน้า UI ตามเมนูที่เลือก
if menu_bar == menu_login:
    st.header("🔐 เข้าสู่ระบบ")
    
    with st.form("login_form"):
        username = st.text_input("👤 ชื่อผู้ใช้")
        password = st.text_input("🔑 รหัสผ่าน", type="password")
        submitted = st.form_submit_button("➡️ เข้าสู่ระบบ")
        
        if submitted:
            if check_user_login(username, password):
                print(username)
                set_username(username)
                st.success("✅ เข้าสู่ระบบสำเร็จ!")
                st.session_state.logged_in = True
                
                # ตั้งค่าสลับเมนูครั้งต่อไป (อย่าแก้ menu_bar ตรงนี้)
                st.session_state.switch_to_menu = "💬 ถาม AI"
                
                ## แสดงข้อความนับถอยหลัง (ถ้าต้องการ)
                # countdown_placeholder = st.empty()
                # for i in range(3, 0, -1):
                #     countdown_placeholder.info(f"ระบบจะรีเฟรชหน้าภายใน {i} วินาที...")
                #     time.sleep(1)
                st.rerun()  # รีรันเพื่อไปหน้าใหม่
            else:
                st.error("❌ ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง")
                
# แสดงหน้า UI ตามเมนูที่เลือก
elif menu_bar == menu_ask:
    username = get_username()

    col1, col2 = st.columns([0.7, 0.3])

    with col1:
        st.title("🤖 Villa Intelligence")

    with col2:
        st.markdown(f"""<div style="margin-top: 35px; margin-bottom: 0px; font-size: 20px; font-weight: 600; text-align: right;">{username}</div>""", unsafe_allow_html=True)

    if "chat_display" not in st.session_state:
        st.session_state.chat_display = []
    if "chat_header" not in st.session_state:
        st.session_state.chat_header = None  # ยังไม่มีหัวข้อ

    def parse_history(text):
        msgs = []
        for line in text.strip().split('\n'):
            if line.startswith("User: "):
                msgs.append({"role": "user", "text": line[6:]})
            elif line.startswith("Bot: "):
                msgs.append({"role": "assistant", "text": line[5:]})
        return msgs
    
    if "current_view" not in st.session_state:
        st.session_state.current_view = "chat"  # ค่าเริ่มต้น

    if st.session_state.get("chat_header") and st.session_state.chat_header.strip() != "":
        history_text = load_history(username, st.session_state.chat_header)
        if history_text:
            st.session_state.chat_display = parse_history(history_text)
    else:
        # กรณียังไม่มีหัวข้อหรือประวัติ ให้เริ่มต้นแชทเปล่า ๆ
        if "chat_display" not in st.session_state:
            st.session_state.chat_display = []

    def chat_input_csv(uploaded_file):
        username = st.session_state.get("username", "guest")

        # แสดงบทสนทนาเดิมที่เกี่ยวข้องกับ CSV จาก session_state
        for msg in st.session_state.get("chat_display_csv", []):
            with st.chat_message(msg["role"]):
                if msg["role"] == "assistant":
                    st.success(msg["text"])
                else:
                    st.info(msg["text"])

        # กล่องพิมพ์คำถามใหม่สำหรับ CSV
        if prompt := st.chat_input("พิมพ์คำถามเกี่ยวกับ CSV..."):
            print(prompt)

            if not st.session_state.get("chat_header"):
                header = generate_header_from_text(prompt)
                st.session_state.chat_header = header
            else:
                header = st.session_state.chat_header
            
            # แสดงคำถามของผู้ใช้
            with st.chat_message("user"):
                st.info(prompt)
            
            # สร้างคำตอบจาก CSV
            with st.spinner("⏳ กำลังวิเคราะห์ข้อมูล CSV..."):
                if check_comparison_header("history_csv", username, header):
                    answer, header = generate_answer_csv_from_memory(username, header, prompt)
                else:
                    answer = generate_csv(uploaded_file, username, header, prompt)

            # แสดงคำตอบของแชทบอท
            with st.chat_message("assistant"):
                st.success(answer)

            # บันทึกลงใน session_state
            st.session_state.chat_display_csv = st.session_state.get("chat_display_csv", []) + [
                {"role": "user", "text": prompt},
                {"role": "assistant", "text": answer},
            ]

    def chat_mode():
        username = st.session_state.get("username", "guest")

        # 1) ถ้ายังไม่มีข้อความใดใน chat_display ให้แสดงข้อความเปิดก่อน
        if not st.session_state.get("chat_display"):
            with st.chat_message("assistant"):
                st.success("สวัสดี! มีอะไรให้เราช่วยไหม ?")

        # 2) แสดงบทสนทนาเดิม
        for msg in st.session_state.get("chat_display", []):
            with st.chat_message(msg["role"]):
                if msg["role"] == "assistant":
                    st.success(msg["text"])
                else:
                    st.info(msg["text"])

        # กล่องพิมพ์คำถามใหม่
        if not st.session_state.get("uploaded_csv"):  # ✅ เช็คว่าไม่มี csv แนบ
            if prompt := st.chat_input("พิมพ์คำถามใหม่..."):
                # แสดงคำถามของผู้ใช้
                with st.chat_message("user"):
                    st.info(prompt)

                # กำหนดหรือสร้างหัวข้อการสนทนา
                if not st.session_state.get("chat_header"):
                    header = generate_header_from_text(prompt)
                    st.session_state.chat_header = header
                else:
                    header = st.session_state.chat_header

                # สร้างคำตอบ
                with st.spinner("⏳ กำลังตอบ..."):
                    answer, header = generate_answer(username, header, prompt)

                # แสดงคำตอบของบอท
                with st.chat_message("assistant"):
                    st.success(answer)

                # บันทึกลงใน session_state
                st.session_state.chat_display = st.session_state.get("chat_display", []) + [
                    {"role": "user", "text": prompt},
                    {"role": "assistant", "text": answer},
                ]

    def history_mode():
        username = st.session_state.get("username", "guest")
        unique_headers = check_header(username)  # [(header, source), ...]

        # สร้าง list แสดง header + แหล่งที่มา
        header_list = [f"{h} [{s}]" for h, s in unique_headers]

       # ส่วนเตรียม placeholder
        placeholder_warning = st.empty()
        
        # ถ้าไม่มีหัวข้อประวัติเลย
        if not header_list:
            st.warning("📭 ยังไม่มีประวัติการพูดคุยให้ลบหรือดู ระบบกำลังนำทางไปยังหน้า Chat!")
            time.sleep(2)  # รอให้ผู้ใช้เห็นข้อความ 2 วินาที
            # เปลี่ยนกลับไปหน้า chat
            st.session_state.current_view = "chat"
            st.rerun()

    
        # ตรวจสอบ confirm_delete ก่อนแสดง selectbox
        confirming = st.session_state.get("confirm_delete", False)

        # ดึงค่า selected เดิม ถ้ามี
        selected_value = st.session_state.get("selected_header_key", None)
        selected_index = header_list.index(selected_value) if selected_value in header_list else 0

        # แสดง selectbox แค่ครั้งเดียว แต่เปิด/ปิดได้
        selected = st.selectbox(
            "📜 ประวัติการพูดคุย (หัวเรื่อง)",
            header_list,
            index=selected_index,
            key="selected_header_key",
            disabled=confirming  # 🔒 ล็อกไม่ให้เลือกได้หากกำลังยืนยันลบ
        )

        # เมื่อมีการยืนยันลบ
        if confirming:
            # —————— บล็อกยืนยันลบ ——————
            st.warning("⚠️ คุณแน่ใจหรือไม่ว่าต้องการลบประวัติการพูดคุยนี้?")
            col_yes, col_no = st.columns(2)

            with col_yes:
                if st.button("✅ ใช่, ลบเลย", key="confirm_delete_yes"):
                    # … โค้ดลบจริง …
                    st.success("✅ ลบเรียบร้อยแล้ว")
                    time.sleep(1)
                    # เคลียร์ state ทั้งหมดที่เกี่ยวข้อง
                    for k in ("chat_display","chat_header","selected_header_key","chat_source","confirm_delete"):
                        st.session_state.pop(k, None)
                    st.rerun()

            with col_no:
                if st.button("❌ ยกเลิก", key="confirm_delete_no"):
                    # แค่เคลียร์ confirm flag แล้วรีรัน
                    st.session_state.confirm_delete = False
                    st.rerun()

            # เมื่ออยู่ใน confirming *จะไม่* รัน else ข้างล่าง
            return

        # —————— บล็อกแสดง selectbox + ปุ่มลบปกติ ——————
        # (จะโผล่ก็ต่อเมื่อกำลังไม่ confirm เท่านั้น)
        # 1) SelectBox
        selected = st.selectbox(
            "📜 ประวัติการพูดคุย (หัวเรื่อง)",
            header_list,
            key="selected_header_key"
        )

        # 2) ปุ่มลบ
        if st.button("🗑️ ลบประวัติการพูดคุยนี้", key="delete_history"):
            # เก็บค่า selected เอาไว้ แล้วสั่งให้เข้า confirming branch
            st.session_state.confirm_delete = True
            st.rerun()

    # … โค้ดโหลดและแสดงบทสนทนา history ตาม selected …

        if selected:
            # แยก header กับ source จาก string ที่เลือก เช่น "ข่าววันนี้ [csv]"
            selected_header = selected.rsplit(" [", 1)[0]
            selected_source = selected.rsplit(" [", 1)[1][:-1]  # เอา ']' ออก

            st.session_state["selected_header"] = selected_header
            st.session_state["selected_source"] = selected_source

            # โหลดประวัติจากแหล่งที่เลือก

            if (selected_source == "text"):
                history_rows = load_history_rows(username, selected_header, source=selected_source)
            elif (selected_source == "csv"): 
                history_rows = load_history_rows(username, selected_header, source=selected_source)
            st.session_state["chat_display"] = []

            chat_display = []
            for user_text, bot_reply in history_rows:
                chat_display.append({"role": "user", "text": user_text})
                chat_display.append({"role": "assistant", "text": bot_reply})

            st.session_state["chat_display"] = chat_display
            st.session_state["chat_header"] = selected_header
            st.session_state["chat_source"] = selected_source

            # แสดงบทสนทนา
            for msg in chat_display:
                with st.chat_message(msg["role"]):
                    if msg["role"] == "assistant":
                        st.success(msg["text"])
                    else:
                        st.info(msg["text"])

            # ต่อบทสนทนาได้เลย
            if prompt := st.chat_input("พิมพ์คำถามเพื่อคุยต่อ..."):
                with st.chat_message("user"):
                    st.info(prompt)

                with st.spinner("⏳ กำลังตอบ..."):
                    answer, header = generate_answer_from_memory(username, selected_header, prompt, source=selected_source)

                with st.chat_message("assistant"):
                    st.success(answer)

                if st.session_state.get("has_csv_attachment", False):
                    save_source = "csv"
                    st.session_state["selected_source"] = "csv"
                else:
                    save_source = selected_source

                st.session_state["chat_display"].extend([
                    {"role": "user", "text": prompt},
                    {"role": "assistant", "text": answer},
                ])

                # เรียกฟังก์ชันบันทึกให้ตรงกับ source
                if save_source == "csv":
                    save_history_csv(username, selected_header, prompt, answer)
                else:
                    save_history(username, selected_header, prompt, answer)         

    # Main
    if "show_history_controls" not in st.session_state:
        st.session_state.show_history_controls = False

    # ก่อนอื่นอย่าเพิ่งสร้าง col1, col2 ทั่วไป
    if st.session_state.current_view == "chat":
        # โหมด Chat — ปุ่ม “ดูประวัติการพูดคุย” จะอยู่ในคอลัมน์กว้าง 3
        col1, col2 = st.columns([3, 1])
    else:
        # โหมด History — ปุ่ม “ลบประวัติการพูดคุยนี้” จะอยู่ในคอลัมน์กว้าง 2.7
        col1, col2 = st.columns([2.6, 1])

    # ฝั่งซ้าย (col1) ใส่ New Chat! เหมือนเดิม
    with col1:
        if st.button("💬 New Chat!", key="new_chat"):
            for k in ("chat_display","chat_header","uploaded_csv"):
                st.session_state.pop(k, None)
            st.session_state.current_view = "chat"
            st.rerun()

    # ฝั่งขวา (col2) ใส่ปุ่มตามโหมด
    with col2:
        if st.session_state.current_view == "chat":
            if st.button("↩️ ดูประวัติการพูดคุย", key="view_history"):
                st.session_state.current_view = "history"
                st.rerun()
        else:
            if st.button("🗑️ ลบประวัติการพูดคุยนี้", key="delete_history"):
                st.session_state.confirm_delete = True
                st.rerun()

    if st.session_state["current_view"] == "chat":
        with st.expander("📎 ขยายเพื่อแนบไฟล์ ", expanded=False):
            uploaded_file = st.file_uploader("📎 แนบไฟล์ ", type=["png", "jpg", "jpeg", "pdf", "csv", "txt"])

        # # ตรงกลาง: selectbox สำหรับเลือกไฟล์ Prompt
        # prompt_files = [f for f in os.listdir(PROMPT_FOLDER) if f.endswith(('.txt', '.json'))]
        # if not prompt_files:
        #     st.warning("ยังไม่มีไฟล์ Prompt ในระบบ")
        # else:
        #     selected_file = st.selectbox("เลือก Prompt สำหรับ LLM", prompt_files, key="selected_file")

        if uploaded_file and uploaded_file.type == "text/csv":
            st.session_state["uploaded_csv"] = uploaded_file
            chat_input_csv(uploaded_file)
        else:
            st.session_state.pop("uploaded_csv", None)
            chat_mode()

    elif st.session_state["current_view"] == "history":
        history_mode()


elif menu_bar == menu_add:
    # ✅ FRONTEND (UI)
    st.header("➕ สร้าง Prompt ใหม่")

    # กล่องใส่ชื่อไฟล์
    new_prompt_name = st.text_input("ชื่อไฟล์ Prompt ใหม่ (ไม่ต้องใส่นามสกุลไฟล์)")

    # เลือกชนิดไฟล์
    file_type = st.radio("เลือกชนิดไฟล์", ["txt", "json"])

    # กล่องใส่เนื้อหา
    new_prompt = st.text_area("พิมพ์ Prompt ใหม่ที่นี่...", height=300)

    # ปุ่มกดเพิ่มไฟล์
    if new_prompt_name and new_prompt:
        if st.button("เพิ่มไฟล์ Prompt"):
            success, message = save_prompt_to_file(None, new_prompt_name, file_type, new_prompt)

            if success:
                st.success(message)
                countdown_placeholder = st.empty()
                for i in range(3, 0, -1):
                    countdown_placeholder.info(f"ระบบจะรีเฟรชหน้าภายใน {i} ...")
                    time.sleep(1)
                st.rerun()
            else:
                st.error(message)

    else:
        st.warning("กรุณากรอกชื่อไฟล์ และเนื้อหา Prompt ก่อนนะคะ")
        add_button = st.button("เพิ่มไฟล์ใหม่")


elif menu_bar == menu_update:
    st.header("📝 อัปเดต/แก้ไข Prompt")

    # อ่านรายชื่อไฟล์ในโฟลเดอร์
    prompt_files = [f for f in os.listdir(PROMPT_FOLDER) if f.endswith(('.txt', '.json'))]

    if not prompt_files:
        st.warning("ยังไม่มีไฟล์ Prompt ในระบบ")
    else:
        # เลือกไฟล์
        selected_file = st.selectbox("เลือก Prompt ที่ต้องการแก้ไข", prompt_files)

        if selected_file:
            file_path = os.path.join(PROMPT_FOLDER, selected_file)

            # โหลดเนื้อหาเดิม
            with open(file_path, 'r', encoding='utf-8') as f:
                current_content = f.read()

            # กล่องแก้ไข
            edited_content = st.text_area("แก้ไข Prompt", current_content, height=300)

            # ปุ่มบันทึก
            if st.button("บันทึกแก้ไข Prompt"):
                status, message = update_prompt_file(file_path, edited_content)

                if status:
                    st.success(message)

                    countdown_placeholder = st.empty()
                    for i in range(3, 0, -1):
                        countdown_placeholder.info(f"ระบบจะรีเฟรชหน้าภายใน {i} ...")
                        time.sleep(1)
                    st.rerun()
                else:
                    st.error(message)


elif menu_bar == menu_delete:
    st.header("🧹 ลบ Prompt")

    # อ่านรายชื่อไฟล์
    prompt_files = [f for f in os.listdir(PROMPT_FOLDER) if f.endswith(('.txt', '.json'))]

    if not prompt_files:
        st.warning("ยังไม่มีไฟล์ Prompt ในระบบ")
    else: 
        # เลือกไฟล์
        file_to_delete = st.selectbox("เลือกไฟล์ Prompt ที่ต้องการลบ", prompt_files)

        if file_to_delete:
            file_path = os.path.join(PROMPT_FOLDER, file_to_delete)

            # แสดงเนื้อหา
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            st.text_area("แสดงเนื้อหา Prompt ที่เลือก", content, height=200, disabled=True)

            # ช่องยืนยันการลบ
            confirm_text = st.text_input(f'พิมพ์ "DELETE {file_to_delete}" เพื่อยืนยันการลบไฟล์')

            if st.button("ลบไฟล์ Prompt"):
                expected_text = f"DELETE {file_to_delete}"
                if confirm_text == expected_text:
                    status, message = delete_prompt_file(file_path)
                    if status:
                        st.success(message)
                        countdown_placeholder = st.empty()
                        for i in range(3, 0, -1):
                            countdown_placeholder.info(f"ระบบจะรีเฟรชหน้าภายใน {i} ...")
                            time.sleep(1)
                        st.rerun()
                    else:
                        st.error(message)
                else:
                    st.warning(f'กรุณาพิมพ์ "{expected_text}" ให้ถูกต้องก่อนลบไฟล์ค่ะ ❗')