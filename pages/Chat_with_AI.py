from utility import *   #
from config import OPENAI_API_KEY

client = OpenAI(api_key=OPENAI_API_KEY)

# เชื่อมต่อ SQLite
conn, cursor = init_db()
initialize_schema(conn)

# ========== ตั้งค่าหน้า Streamlit ==========
st.page_link("app.py", label="⬅️ กลับหน้าหลัก", icon="🏠")
st.title("🤖 AI Chat Platform")
#---------------
# # ✅ ตรวจ login และสิทธิ์
if "user_id" not in st.session_state or st.session_state.get("status") != "APPROVED":
    st.error("🚫 กรุณาเข้าสู่ระบบ และรอการอนุมัติ")
    st.stop()
#---------------
with st.sidebar:
    st.markdown("### 📑 เมนูหลัก")
    tab_choice = st.radio("เลือกเมนู", [
        "💬 สนทนากับ GPT",
        "🧠 สนทนากับ Prompt",
        "📜 ประวัติการสนทนา",
        "📘 วิธีการใช้งาน"
    ])
    # ✅ ปุ่ม Reset ตามแต่ละ tab
    if st.button("🆕 เริ่มแชทใหม่"):
        st.session_state.clear()
        st.rerun()
#---------------
# ========== TAB 1: Chat with GPT ==========
if tab_choice == "💬 สนทนากับ GPT":
    st.subheader("💬 สนทนากับ GPT")
    st.caption("🚀 A Streamlit chatbot powered by OpenAI GPT-3.5/4")

    tab_chat, tab_file = st.tabs(["💬 แชททั่วไป", "📁 แชทพร้อมไฟล์"])

    with tab_chat:
        st.caption("💬 ใช้ Prompt เพื่อคุยกับ GPT ในบริบทที่กำหนด เช่น นักบัญชี นักกฎหมาย ฯลฯ")
           
        # ✅ สร้าง session ครั้งแรกหากยังไม่มี
        st.session_state.setdefault("messages_gpt", [
            {"role": "assistant", "content": "How can I help you?"}
        ])

        # ✅ แสดงบทสนทนาเดิม
        for msg in st.session_state["messages_gpt"]:
            st.chat_message(msg["role"]).write(msg["content"])

        # ✅ รอรับข้อความใหม่จากผู้ใช้
        if prompt := st.chat_input("พิมพ์ข้อความของคุณ...", key="chat_gpt_input"):
            st.chat_message("user").write(prompt)
            st.session_state["messages_gpt"].append({"role": "user", "content": prompt})
            try:
                response = client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=st.session_state["messages_gpt"]
                )
                reply = response.choices[0].message.content
            except Exception as e:
                reply = f"❌ Error: {e}"
            st.chat_message("assistant").write(reply)
            st.session_state["messages_gpt"].append({"role": "assistant", "content": reply})

        # ✅ ปุ่มบันทึกบทสนทนา
        if st.button("💾 บันทึกบทสนทนา", key="save_gpt_button"):
            messages = st.session_state["messages_gpt"]
            if len(messages) <= 1:
                st.warning("⚠️ ขอโทษ ไม่มีข้อความที่สามารถบันทึกได้")
            else:
                title = generate_title_from_conversation(messages)
                save_conversation(conn, cursor, title, "chat_gpt", messages)
                st.success(f"✅ บันทึกแล้ว: {title}")

    # ----- TAB: แชทพร้อมไฟล์ -----
    with tab_file:
        st.caption("📂 วิเคราะห์ไฟล์ด้วย Prompt หรือถามจากเวกเตอร์")
        uploaded_file = st.file_uploader("📂 กรุณาอัปโหลดไฟล์", type=["txt", "md", "csv"], key="file_upload")          
        if uploaded_file and OPENAI_API_KEY and "chain" not in st.session_state:
            process_file_to_chain(uploaded_file)

        if "chain" in st.session_state:
            st.markdown("---")
            st.info("💬 ถามจากเวกเตอร์ (Vector Search)")
            chat_with_vector_chain()

        if st.session_state.get("chat_history"):
            if st.button("💾 บันทึกบทสนทนา", key="save_file_button"):
                messages = st.session_state["chat_history"]
                title = generate_title_from_conversation(messages)
                save_conversation(conn, cursor, title, "chat_file", messages)
                st.success(f"✅ บันทึกแล้ว: {title}")
                
# ========== Choice 2: เพิ่ม/เลือก Prompt ==========
elif tab_choice == "🧠 สนทนากับ Prompt":
    st.subheader("🧠 สนทนากับ Prompt")

    tab_chat, tab_file, tab_manage = st.tabs([
        "💬 Prompt สำหรับแชททั่วไป",
        "📁 Prompt พร้อมไฟล์",
        "✍️ บันทึก / จัดการ Prompt"
    ])

    # ===== TAB 1: 💬 Prompt สำหรับแชททั่วไป =====
    with tab_chat:
        st.caption("💬 ใช้ Prompt เพื่อคุยกับ GPT ในบริบทที่กำหนด เช่น นักบัญชี นักกฎหมาย ฯลฯ")
        prompts = list_prompts()
        prompt_dict = {name: content for name, content in prompts}

        if prompt_dict:
            selected_prompt_name = st.selectbox("🧠 เลือก Prompt", list(prompt_dict.keys()), key="prompt_selector_chat")
            selected_prompt = prompt_dict[selected_prompt_name]

            with st.expander("📜 ข้อความ Prompt ที่เลือก"):
                st.code(selected_prompt)

            st.session_state.setdefault("messages_prompt", [])
            if not st.session_state["messages_prompt"] or st.session_state.get("active_prompt") != selected_prompt_name:
                st.session_state["messages_prompt"] = [{"role": "system", "content": selected_prompt}]
                st.session_state["active_prompt"] = selected_prompt_name

            for msg in st.session_state["messages_prompt"]:
                if msg["role"] != "system":
                    st.chat_message(msg["role"]).write(msg["content"])

            if prompt := st.chat_input("💬 พิมพ์ข้อความของคุณ"):
                st.chat_message("user").write(prompt)
                st.session_state["messages_prompt"].append({"role": "user", "content": prompt})

                try:
                    response = client.chat.completions.create(
                        model="gpt-3.5-turbo",
                        messages=st.session_state["messages_prompt"]
                    )
                    reply = response.choices[0].message.content
                except Exception as e:
                    reply = f"❌ Error: {e}"

                st.chat_message("assistant").write(reply)
                st.session_state["messages_prompt"].append({"role": "assistant", "content": reply})

            if st.button("💾 บันทึกบทสนทนา", key="save_prompt_chat_chat"):
                messages = st.session_state["messages_prompt"]
                if len(messages) <= 1:
                    st.warning("⚠️ ไม่มีข้อความเพียงพอสำหรับบันทึก")
                else:
                    title = generate_title_from_conversation(messages)
                    save_conversation(conn, cursor, title, "chat_gpt", messages)
                    st.success(f"✅ บันทึกแล้ว: {title}")
        else:
            st.warning("⚠️ ยังไม่มี Prompt กรุณาเพิ่มที่แท็บ '✍️ บันทึก / จัดการ Prompt'")

    # ===== TAB 2: 📁 Prompt พร้อมไฟล์ =====
    with tab_file:
        st.caption("📂 วิเคราะห์ไฟล์ด้วย Prompt หรือถามจากเวกเตอร์")
        prompts = list_prompts()
        prompt_dict = {name: content for name, content in prompts}
        selected_prompt = None

        if prompt_dict:
            selected_prompt_name = st.selectbox("🧠 เลือก Prompt", list(prompt_dict.keys()), key="prompt_selector_tab_file")
            selected_prompt = prompt_dict[selected_prompt_name]
            with st.expander("📜 แสดงเนื้อหา Prompt"):
                st.code(selected_prompt)
        else:
            st.warning("⚠️ ยังไม่มี Prompt กรุณาเพิ่มก่อนเริ่ม")

        uploaded_file = st.file_uploader("📂 อัปโหลดไฟล์ (.txt, .md, .csv, .xlsx)", type=["txt", "md", "csv", "xlsx"], key="file_upload_tab_file")

        if uploaded_file and selected_prompt and "chain" not in st.session_state:
            process_uploaded_file_for_prompt(uploaded_file)
            process_file_to_chain(uploaded_file)

        if "chain" in st.session_state:
            st.markdown("---")
            st.info("💬 ถามจากเนื้อหาไฟล์ (Vector Search)")
            chat_with_vector_chain()

        if selected_prompt and st.session_state.get("file_content"):
            if st.button("📊 วิเคราะห์เนื้อหาทั้งหมดด้วย Prompt นี้"):
                analyze_all_chunks_with_prompt(selected_prompt, selected_prompt_name)

        if st.session_state.get("messages_prompt_file_analysis"):
            st.markdown("---")
            st.info("🧠 ถามต่อจากผลการวิเคราะห์ Prompt")

            messages = st.session_state["messages_prompt_file_analysis"]
            for msg in messages:
                if msg["role"] != "system":
                    st.chat_message(msg["role"]).write(msg["content"])

            if prompt := st.chat_input("💬 ถามเกี่ยวกับผลวิเคราะห์ Prompt", key="chat_prompt_followup"):
                st.chat_message("user").write(prompt)
                messages.append({"role": "user", "content": prompt})

                try:
                    response = client.chat.completions.create(
                        model="gpt-3.5-turbo",
                        messages=messages
                    )
                    reply = response.choices[0].message.content
                except Exception as e:
                    reply = f"❌ Error: {e}"

                st.chat_message("assistant").write(reply)
                messages.append({"role": "assistant", "content": reply})

            with st.expander("📥 ดาวน์โหลดผลลัพธ์จาก Prompt"):
                prepare_download_response(source_key="messages_prompt_file_analysis", key_suffix="download_prompt_file")

            if st.button("💾 บันทึกบทสนทนา Prompt", key="save_prompt_file_chat"):
                messages = st.session_state["messages_prompt_file_analysis"]
                if len(messages) <= 1:
                    st.warning("⚠️ ไม่มีข้อความเพียงพอสำหรับบันทึก")
                else:
                    title = generate_title_from_conversation(messages)
                    save_conversation(conn, cursor, title, "chat_file", messages)
                    st.success(f"✅ บันทึกแล้ว: {title}")

    # ===== TAB 3: ✍️ บันทึก / จัดการ Prompt =====
    with tab_manage:
        st.caption("✍️ เพิ่ม ลบ หรือแก้ไข Prompt ที่ใช้ในระบบ")

        # ===== เพิ่ม Prompt ใหม่ =====
        prompt_name = st.text_input("📝 ตั้งชื่อ Prompt ใหม่", key="prompt_name_input_create")
        prompt_content = st.text_area("📄 เนื้อหา Prompt", height=120, key="prompt_content_input_create")
        if st.button("💾 บันทึก Prompt", key="save_prompt_create"):
            if prompt_name and prompt_content:
                save_prompt(prompt_name, prompt_content)
                st.success(f"✅ บันทึก Prompt “{prompt_name}” เรียบร้อยแล้ว")
                st.experimental_rerun()
            else:
                st.warning("⚠️ กรุณากรอกชื่อและเนื้อหา Prompt")

        # ===== รายการ Prompt ที่มี พร้อมแก้ไข/ลบ =====
        prompts = list_prompts()
        if prompts:
            st.markdown("### 🗂 รายการ Prompt ที่มี")
            for name, content in prompts:
                with st.expander(f"📌 {name}", expanded=False):
                    edited_content = st.text_area("🔧 แก้ไขเนื้อหา Prompt", value=content, height=150, key=f"edit_{name}")

                    col1, col2 = st.columns([1, 1])
                    with col1:
                        if st.button("💾 บันทึกการแก้ไข", key=f"save_edit_{name}"):
                            save_prompt(name, edited_content)
                            st.success(f"✅ แก้ไข Prompt “{name}” เรียบร้อยแล้ว")
                            st.rerun()  # ✅ ใช้ตัวนี้แทน experimental_rerun()

                        if st.button("🗑️ ลบ Prompt นี้", key=f"delete_prompt_{name}"):
                            delete_prompt(name)
                            st.success(f"✅ ลบแล้ว: {name}")
                            st.rerun()  # ✅ เช่นกัน
        else:
            st.info("ℹ️ ยังไม่มี Prompt ในระบบ")
               
# ========== Choice 4: History ==========
elif tab_choice == "📜 ประวัติการสนทนา":
    st.subheader("📜 ประวัติการสนทนา")

    if "messages_history" not in st.session_state:
        st.session_state["messages_history"] = []

    convs = list_conversations()
    label_map = {f"{name} ({created_at})": conv_id for conv_id, name, created_at in convs}
    selected = st.selectbox("📁 เลือกบทสนทนา", ["- เลือก -"] + list(label_map.keys()))

    if selected != "- เลือก -":
        conv_id = label_map[selected]
        cursor.execute("SELECT role, content FROM messages WHERE conversation_id = ? ORDER BY id", (conv_id,))
        messages = [{"role": r, "content": c} for r, c in cursor.fetchall()]

        if not st.session_state["messages_history"] or st.session_state.get("conv_id") != conv_id:
            st.session_state["messages_history"] = messages
            st.session_state["conv_id"] = conv_id

        for msg in st.session_state["messages_history"]:
            st.chat_message(msg["role"]).write(msg["content"])

        if prompt := st.chat_input("💬 พิมพ์ข้อความเพื่อต่อบทสนทนา", key="chat_continue_input"):
            st.chat_message("user").write(prompt)
            st.session_state["messages_history"].append({"role": "user", "content": prompt})

            try:
                response = client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=st.session_state["messages_history"]
                )
                reply = response.choices[0].message.content
            except Exception as e:
                reply = f"❌ Error: {e}"

            st.chat_message("assistant").write(reply)
            st.session_state["messages_history"].append({"role": "assistant", "content": reply})

        if st.button("💾 อัปเดตบทสนทนานี้", key="update_this_conversation"):
            cursor.execute("DELETE FROM messages WHERE conversation_id = ?", (conv_id,))
            for msg in st.session_state["messages_history"]:
                cursor.execute(
                    "INSERT INTO messages (conversation_id, role, content) VALUES (?, ?, ?)",
                    (conv_id, msg["role"], msg["content"])
                )
            conn.commit()
            st.success("✅ อัปเดตบทสนทนาเดิมเรียบร้อยแล้ว")
        with st.expander("🗑️ ลบบทสนทนานี้"):
            if st.button("ยืนยันการลบ", key="confirm_delete_conv"):
                cursor.execute("DELETE FROM messages WHERE conversation_id = ?", (conv_id,))
                cursor.execute("DELETE FROM conversations WHERE id = ?", (conv_id,))
                conn.commit()
                st.session_state["messages_history"] = []
                st.success("✅ ลบบทสนทนาเรียบร้อยแล้ว")
                st.stop()
        # ✅ ปุ่มดาวน์โหลดบทสนทนาเป็นไฟล์
        if st.session_state.get("messages_history"):
            with st.expander("📥 ดาวน์โหลดบทสนทนาเป็นไฟล์"):
                file_format = st.selectbox("เลือกรูปแบบไฟล์", ["txt", "md"], key="history_download_format")
                file_name = st.text_input("📄 ตั้งชื่อไฟล์", value="chat_history", key="history_download_filename")

                # สร้างเนื้อหาไฟล์จากข้อความ
                content_lines = []
                for msg in st.session_state["messages_history"]:
                    role = msg["role"].capitalize()
                    text = msg["content"]
                    if file_format == "md":
                        content_lines.append(f"**{role}:**\n{text}\n")
                    else:
                        content_lines.append(f"{role}:\n{text}\n")

                file_content = "\n".join(content_lines)
                mime_type = "text/plain" if file_format == "txt" else "text/markdown"
                full_filename = f"{file_name.strip()}.{file_format}"

                st.download_button(
                    label="⬇️ ดาวน์โหลดไฟล์",
                    data=file_content,
                    file_name=full_filename,
                    mime=mime_type
                )

# ========== Choice 5 : วิธีการใช้งาน ==========
if tab_choice == "📘 วิธีการใช้งาน":
    st.subheader("📘 วิธีการใช้งานโปรแกรม")
    tab_intro, tab_howto, tab_tip = st.tabs(["🧩 คุณสมบัติของโปรแกรม", "💡 วิธีใช้งาน Chatai","💡 เคล็ดลับเพิ่มเติม"])

    with tab_intro:
        st.subheader("🧩 คุณสมบัติของโปรแกรม")
        st.markdown("""
        ระบบนี้ถูกออกแบบมาให้สามารถสนทนากับ AI ได้หลากหลายรูปแบบ ไม่ว่าจะเป็นการถามตอบทั่วไป การวิเคราะห์จากไฟล์ หรือการใช้ Prompt เฉพาะทาง พร้อมทั้งบันทึกและจัดการประวัติการสนทนาได้

        ### 🧱 โครงสร้างไฟล์หลักของโปรแกรม
        ```plaintext
        ai_chat_platform/
        ├── app.py                 # 🎯 หน้าเรียกใช้งานหลัก
        ├── utility.py             # 🧠 รวมฟังก์ชันสำหรับจัดการฐานข้อมูล และการสนทนา
        ├── .env                   # 🔐 เก็บ API Key แบบปลอดภัย
        ├── /pages/
        │   ├── Chat_with_AI.py    # 💬 หน้าแชทหลัก
        │   ├── History.py         # 📜 แสดงประวัติการสนทนา
        │   ├── Prompt_add.py      # 🧠 สร้างและเลือก Prompt
        ├── /data/
        │   ├── sqdata.db          # 🗂 ไฟล์ฐานข้อมูล SQLite
        │   └── schema.sql         # 📄 ไฟล์สร้างโครงสร้างฐานข้อมูล
        
        🛠 ความสามารถหลักของระบบ
        ✅ สนทนากับ GPT-3.5/4 ได้แบบทันที
        ✅ วิเคราะห์ไฟล์ .txt, .md, .csv ได้โดยตรง
        ✅ สร้างและจัดการ Prompt สำหรับคำถามเฉพาะ
        ✅ บันทึก และแชทต่อจากประวัติเดิมได้
        ✅ รองรับการใช้งานร่วมกับ LIFF หรือระบบอื่นในอนาคต
        """)

    with tab_howto:
        st.subheader("📝 วิธีใช้งานแต่ละเมนู")
        st.markdown("""
        Chatai ถูกออกแบบให้ใช้งานง่ายผ่าน 4 เมนูหลักทางด้านซ้ายของหน้าจอ โดยสามารถทำงานร่วมกับ GPT-3.5/4 และเอกสารต่าง ๆ ได้ทันที

        ---

        ### 1️⃣  💬 สนทนากับ GPT
        tab 1 วิเคราะห์ไฟล์เอกสาร (📄 คุยกับไฟล์)
        - เหมาะสำหรับถามตอบทั่วไป
        - สามารถเริ่มสนทนาใหม่ได้ทุกครั้งด้วยปุ่ม **"🆕 เริ่มแชทใหม่"**
        - พิมพ์คำถามในกล่องด้านล่าง แล้วรอรับคำตอบจาก GPT
        - สามารถบันทึกบทสนทนาไว้ใช้งานภายหลังได้ด้วยปุ่ม **"💾 บันทึกบทสนทนา"**
        tab 2 วิเคราะห์ไฟล์เอกสาร (📄 คุยกับไฟล์)               
        - รองรับ `.txt`, `.md`, `.csv`
        - เลือกไฟล์ > คลิก "▶️ ประมวลผลไฟล์"
        - สามารถถามคำถามที่เกี่ยวข้องกับเนื้อหาในไฟล์ได้
        - บันทึกบทสนทนาเกี่ยวกับเอกสารด้วยปุ่ม "💾 บันทึกบทสนทนา"

        ---

        ### 3️⃣ ใช้ Prompt เฉพาะทาง (🧠 เพิ่ม/เลือก Prompt)
        - สร้าง Prompt พิเศษเพื่อกำหนดบทบาทหรือบริบทของ GPT (เช่น นักบัญชี, นักกฎหมาย, ที่ปรึกษา ฯลฯ)
        - เลือก Prompt ที่ต้องการ แล้วเริ่มสนทนาในบริบทนั้นได้ทันที
        - แนบไฟล์เพื่อให้ GPT วิเคราะห์ร่วมกับ Prompt ก็ได้
        - สามารถลบหรือแก้ไข Prompt ได้ภายหลัง

        ---

        ### 4️⃣ ประวัติการสนทนา (📜 แชทต่อจากบทสนทนาเดิม)
        - ดูบทสนทนาเดิมทั้งหมดที่เคยบันทึกไว้
        - เลือกบทสนทนา > แชทต่อจากจุดเดิมได้เลย
        - สามารถอัปเดต/แก้ไขบทสนทนาเดิมและบันทึกซ้ำได้
        - **มีปุ่มลบประวัติ** สำหรับบทสนทนาที่ไม่ต้องการเก็บไว้

        ---
        💡 **แนะนำ:** ทุกการใช้งานสามารถใช้ได้ฟรีผ่าน GPT-3.5 หรือเปลี่ยนเป็น GPT-4 (ถ้ามี API Key ที่รองรับ)
        """)
        with tab_tip:
            st.markdown("""
        ## 💡 เคล็ดลับการใช้งานอย่างมีประสิทธิภาพ

        ---

        ### 🧠 สร้าง Prompt แบบเฉพาะทาง
        เช่น:
        - “คุณเป็นนักบัญชี ให้แนะนำเรื่องการเงิน”
        - “คุณคือทนายความ ให้ตอบตามหลักกฎหมาย”

        การกำหนดบทบาทจะทำให้คำตอบแม่นยำและตรงตามความคาดหวังมากขึ้น

        ---

        ### 📂 เลือกประเภทไฟล์ให้เหมาะสม
        - ใช้ `.txt` หรือ `.csv` หากมีข้อมูลจำนวนมาก → โหลดเร็วและไม่ซับซ้อน
        - ใช้ `.xlsx` เฉพาะเมื่อจำเป็นต้องใช้โครงสร้างตารางแบบ Excel

        **แนะนำ:** แปลง `.xlsx` เป็น `.csv` หากข้อมูลไม่ซับซ้อนมาก เพื่อให้ประมวลผลเร็วขึ้น

        ---

        ### 🔄 ใช้ปุ่ม “🆕 เริ่มแชทใหม่”
        - ทุกแท็บมีปุ่มนี้ เพื่อเริ่มต้นสนทนาใหม่จากศูนย์
        - เหมาะเมื่อเปลี่ยนบริบทคำถาม หรือมีข้อมูลใหม่

        ---

        ### 📥 ดาวน์โหลดผลลัพธ์หลายรูปแบบ
        - สามารถเลือกบันทึกในฟอร์แมตต่าง ๆ:
        - `.txt` → ใช้ทั่วไป
        - `.md` → สำหรับ Markdown
        - `.csv` → เหมาะกับข้อมูลตาราง
        - `.xlsx` → สำหรับการเปิดใน Excel

        ---

        ### 💾 อย่าลืมบันทึกบทสนทนา
        - คลิกปุ่ม “💾 บันทึกบทสนทนา” เพื่อเก็บบทสนทนาไว้ใช้ภายหลัง
        - สามารถดูย้อนหลังได้ในเมนู **📜 ประวัติการสนทนา**
        - แชทต่อจากเดิม หรืออัปเดตบทสนทนาเก่าได้

        ---
        """)