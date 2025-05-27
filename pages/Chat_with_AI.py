from utility import *  # ฟังก์ชันทั้งหมด + libary
# ===== โหลด API Key =====
load_dotenv()
open_ai_key = os.getenv("openai_api_key")
client = OpenAI(api_key=open_ai_key)

# เชื่อมต่อ SQLite
conn, cursor = init_db()
initialize_schema(conn)

# ========== ตั้งค่าหน้า Streamlit ==========
st.set_page_config(page_title="AI Chat Platform", page_icon="🤖", layout="wide")
st.page_link("app.py", label="⬅️ กลับหน้าหลัก", icon="🏠")
st.title("🤖 AI Chat Platform")
#---------------
# ✅ ตรวจ login และสิทธิ์
if "user_id" not in st.session_state or st.session_state.get("status") != "APPROVED":
    st.error("🚫 กรุณาเข้าสู่ระบบ และรอการอนุมัติ")
    st.stop()
#---------------
with st.sidebar:
    st.markdown("### 📑 เมนูหลัก")
    tab_choice = st.radio("เลือกเมนู", [
        "💬 สนทนากับ GPT",
        "📄 คุยกับไฟล์",
        "🧠 เพิ่ม/เลือก Prompt",
        "📜 แชทต่อจากบทสนทนาเดิม",
        "📘 วิธีการใช้งาน"
    ])
#---------------
# ========== TAB 1: Chat with GPT ==========
if tab_choice == "💬 สนทนากับ GPT":
    st.subheader("💬 สนทนากับ GPT")
    st.caption("🚀 A Streamlit chatbot powered by OpenAI GPT-3.5/4")

    if st.button("🆕 เริ่มแชทใหม่"):
        st.session_state["messages_gpt"] = [
            {"role": "assistant", "content": "How can I help you?"}
        ]

    if "messages_gpt" not in st.session_state:
        st.session_state["messages_gpt"] = [
            {"role": "assistant", "content": "How can I help you?"}
        ]

    for msg in st.session_state["messages_gpt"]:
        st.chat_message(msg["role"]).write(msg["content"])

    if prompt := st.chat_input("Type your message...", key="chat_gpt_input"):
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

    if st.button("💾 บันทึกบทสนทนา", key="save_gpt_button"):
        messages = st.session_state["messages_gpt"]
        if len(messages) <= 1:
            st.warning("⚠️ ขอโทษ ไม่มีข้อความที่สามารถบันทึกได้")
        else:
            title = generate_title_from_conversation(messages)
            save_conversation(conn, cursor, title, "chat_gpt", messages)
            st.success(f"✅ บันทึกแล้ว: {title}")

        

# ========== TAB 2: Chat with File ==========
elif tab_choice == "📄 คุยกับไฟล์":
    st.subheader("📄 คุยกับไฟล์ของคุณ")
    st.caption("📁 รองรับไฟล์ .txt, .md, .csv")

    uploaded_file = st.file_uploader("📂 กรุณาอัปโหลดไฟล์", type=["txt", "md", "csv"], key="file_upload")

    if uploaded_file and open_ai_key:
        if st.button("▶️ ประมวลผลไฟล์"):
            with open("temp_input.txt", "wb") as f:
                f.write(uploaded_file.getbuffer())

            loader = TextLoader("temp_input.txt", encoding="utf-8")
            docs = loader.load()

            text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
            split_docs = text_splitter.split_documents(docs)

            embeddings = OpenAIEmbeddings(openai_api_key=open_ai_key)
            vectorstore = Chroma.from_documents(split_docs, embeddings)

            chain = ConversationalRetrievalChain.from_llm(
                llm=ChatOpenAI(temperature=0, openai_api_key=open_ai_key),
                retriever=vectorstore.as_retriever(),
                memory=ConversationBufferMemory(memory_key="chat_history", return_messages=True),
            )

            st.session_state["chain"] = chain
            st.session_state["chat_history"] = []

    if "chain" in st.session_state:
        for msg in st.session_state["chat_history"]:
            st.chat_message(msg["role"]).write(msg["content"])

        if prompt := st.chat_input("พิมพ์คำถามของคุณเกี่ยวกับไฟล์นี้", key="chat_file_input"):
            st.chat_message("user").write(prompt)
            st.session_state["chat_history"].append({"role": "user", "content": prompt})

            try:
                response = st.session_state["chain"].run(prompt)
            except Exception as e:
                response = f"❌ เกิดข้อผิดพลาด: {e}"

            st.chat_message("assistant").write(response)
            st.session_state["chat_history"].append({"role": "assistant", "content": response})

    if st.session_state.get("chat_history"):
        if st.button("💾 บันทึกบทสนทนา", key="save_file_button"):
            messages = st.session_state["chat_history"]
            title = generate_title_from_conversation(messages)
            save_conversation(conn, cursor, title, "chat_file", messages)
            st.success(f"✅ บันทึกแล้ว: {title}")

# ========== TAB 3: Prompt ==========
elif tab_choice == "🧠 เพิ่ม/เลือก Prompt":
    st.subheader("🧠 เพิ่ม/เลือก Prompt")

    if "messages_prompt" not in st.session_state:
        st.session_state["messages_prompt"] = []

    with st.expander("➕ บันทึก Prompt ใหม่"):
        prompt_name = st.text_input("ชื่อ Prompt", key="prompt_name_input")
        prompt_content = st.text_area("ข้อความ Prompt", height=120, key="prompt_content_input")
        if st.button("💾 บันทึก Prompt"):
            if prompt_name and prompt_content:
                save_prompt(prompt_name, prompt_content)
                st.session_state["prompt_saved"] = prompt_name
            else:
                st.warning("⚠️ กรุณากรอกชื่อและข้อความ Prompt ให้ครบ")

        if "prompt_saved" in st.session_state:
            st.success(f"✅ บันทึก Prompt “{st.session_state['prompt_saved']}” เรียบร้อยแล้ว")
            st.info("🔁 กรุณารีเฟรชหน้าเพื่ออัปเดตรายชื่อ Prompt")

    prompts = list_prompts()
    prompt_dict = {name: content for name, content in prompts}

    if prompt_dict:
        selected_prompt_name = st.selectbox("เลือก Prompt", list(prompt_dict.keys()))
        selected_prompt = prompt_dict[selected_prompt_name]

        col1, col2 = st.columns([3, 1])
        with col1:
            st.info(f"💡 **ข้อความ Prompt:**\n\n{selected_prompt}")
        with col2:
            if st.button("🗑️ ลบ Prompt นี้"):
                delete_prompt(selected_prompt_name)
                st.success(f"✅ ลบ Prompt “{selected_prompt_name}” แล้ว")
                st.experimental_set_query_params(deleted="true")
                st.stop()

        st.markdown("---")
        st.subheader("💬 เริ่มต้นสนทนาโดยใช้ Prompt นี้")

        if not st.session_state["messages_prompt"] or st.session_state.get("active_prompt") != selected_prompt_name:
            st.session_state["messages_prompt"] = [{"role": "system", "content": selected_prompt}]
            st.session_state["active_prompt"] = selected_prompt_name

        for msg in st.session_state["messages_prompt"]:
            if msg["role"] != "system":
                st.chat_message(msg["role"]).write(msg["content"])

        if prompt := st.chat_input("พิมพ์ข้อความของคุณ", key="chat_prompt_input"):
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

        uploaded_file = st.file_uploader("📁 เลือกไฟล์ (.txt, .md, .csv)", type=["txt", "md", "csv"], key="file_prompt_upload")
        if uploaded_file:
            file_content = uploaded_file.read().decode("utf-8")
            st.text_area("📄 แสดงเนื้อหาไฟล์", file_content, height=200, disabled=True)

            if st.button("📊 วิเคราะห์ไฟล์ด้วย Prompt นี้"):
                try:
                    gpt_messages = [
                        {"role": "system", "content": selected_prompt},
                        {"role": "user", "content": f"กรุณาวิเคราะห์เนื้อหานี้:\n\n{file_content}"}
                    ]
                    response = client.chat.completions.create(
                        model="gpt-3.5-turbo",
                        messages=gpt_messages
                    )
                    reply = response.choices[0].message.content
                except Exception as e:
                    reply = f"❌ Error: {e}"

                st.success("✅ วิเคราะห์เรียบร้อยแล้ว! เริ่มสนทนาได้ต่อเลย")
                st.session_state["messages_prompt"] = gpt_messages + [{"role": "assistant", "content": reply}]
                st.session_state["active_prompt"] = selected_prompt_name
                st.chat_message("assistant").write(reply)

        if st.session_state.get("messages_prompt"):
            if st.button("💾 บันทึกบทสนทนา", key="save_prompt_button"):
                messages = st.session_state["messages_prompt"]
                title = generate_title_from_conversation(messages)
                save_conversation(conn, cursor, title, "chat_file", messages)
                st.success(f"✅ บันทึกแล้ว: {title}")

# ========== TAB 4: History ==========
elif tab_choice == "📜 แชทต่อจากบทสนทนาเดิม":
    st.subheader("📜 แชทต่อจากบทสนทนาเดิม")

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
                             
# ========== TAB 5 : วิธีการใช้งาน ==========
if tab_choice == "📘 วิธีการใช้งาน":
    st.subheader("📘 วิธีการใช้งานโปรแกรม")
    tab_intro, tab_howto = st.tabs(["🧩 คุณสมบัติของโปรแกรม", "💡 วิธีใช้งาน Chatai"])

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
        st.subheader("💡 วิธีใช้งาน Chatai")
        st.markdown("""
        Chatai ถูกออกแบบให้ใช้งานง่ายผ่าน 4 เมนูหลักทางด้านซ้ายของหน้าจอ โดยสามารถทำงานร่วมกับ GPT-3.5/4 และเอกสารต่าง ๆ ได้ทันที

        ---

        ### 1️⃣ เริ่มต้นแชทใหม่ (💬 สนทนากับ GPT)
        - เหมาะสำหรับถามตอบทั่วไป
        - สามารถเริ่มสนทนาใหม่ได้ทุกครั้งด้วยปุ่ม **"🆕 เริ่มแชทใหม่"**
        - พิมพ์คำถามในกล่องด้านล่าง แล้วรอรับคำตอบจาก GPT
        - สามารถบันทึกบทสนทนาไว้ใช้งานภายหลังได้ด้วยปุ่ม **"💾 บันทึกบทสนทนา"**

        ---

        ### 2️⃣ วิเคราะห์ไฟล์เอกสาร (📄 คุยกับไฟล์)
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

        ### 4️⃣ ดูและแชทต่อจากประวัติเดิม (📜 แชทต่อจากบทสนทนาเดิม)
        - ดูบทสนทนาเดิมทั้งหมดที่เคยบันทึกไว้
        - เลือกบทสนทนา > แชทต่อจากจุดเดิมได้เลย
        - สามารถอัปเดต/แก้ไขบทสนทนาเดิมและบันทึกซ้ำได้
        - **มีปุ่มลบประวัติ** สำหรับบทสนทนาที่ไม่ต้องการเก็บไว้

        ---
        💡 **แนะนำ:** ทุกการใช้งานสามารถใช้ได้ฟรีผ่าน GPT-3.5 หรือเปลี่ยนเป็น GPT-4 (ถ้ามี API Key ที่รองรับ)
        """)