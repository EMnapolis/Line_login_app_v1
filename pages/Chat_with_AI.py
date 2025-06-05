#page/chat_with_ai.py
from utility_chat import *   #ทุกอย่างจากไฟล์ utility.py
from config import OPENAI_API_KEY
from dotenv import load_dotenv
load_dotenv()

client = OpenAI(api_key=OPENAI_API_KEY)
# เชื่อมต่อ SQLite
conn, cursor = init_db()
initialize_schema(conn)

# ============================
# 🌐 GLOBAL PATHS & CONSTANTS
# ============================

# ชื่อตารางในฐานข้อมูล
TABLE_NAME_CHAT = "chat_gpt"
TABLE_NAME_PROMPT = "prompt_store"

# คีย์ใน session_state
KEY_MESSAGES = "messages_gpt"
KEY_ANALYSIS_RESULT = "analysis_result"
KEY_SHOW_DOWNLOAD = "show_download"
KEY_CHAT_HISTORY = "chat_all_in_one"
KEY_SELECTED_PROMPT = "prompt_selector"

# MIME types
MIME_TYPES = {
    "txt": "text/plain",
    "md": "text/markdown",
}
file_content = ""
# ชื่อไฟล์เริ่มต้น
DEFAULT_FILENAME = "analysis_result"

# System prompt เริ่มต้น
DEFAULT_SYSTEM_PROMPT = "คุณคือผู้ช่วยที่สามารถตอบคำถามทั่วไป และใช้เนื้อหาจากไฟล์หากมี"

# ========== ตั้งค่าหน้า Streamlit ==========
CHAT_TOKEN_VL = os.getenv("CHAT_TOKEN") or "Empty" #Set ตัวแปร chat_token_vl

# DB_FILE = os.path.join("data", "sqdata.db")
# def get_connection():
#     return sqlite3.connect(DB_FILE)
# ========== Role ==========
role = st.session_state.get("Role", "")


# ----------------------------
# ⚙️ Debug Mode Configuration
# ----------------------------
DEBUG = os.getenv("DEBUG", "0") == "1"

if DEBUG:
    # ตั้งค่า session ผู้ใช้ mock สำหรับการทดสอบ
    if "user_id" not in st.session_state:
        st.session_state["user_id"] = "Udebug123456"
        st.session_state["displayName"] = "U TEST"
        st.session_state["pictureUrl"] = "https://i.imgur.com/1Q9Z1Zm.png"
        st.session_state["status"] = "APPROVED"
        st.session_state["Role"] = "user"
        st.info("🔧 Loaded mock user session for debugging.")


#def render_page():
st.page_link("app.py", label="⬅️ กลับหน้าหลัก", icon="🏠")
st.title("🤖 AI Chat Platform")
#---------------
# ✅ ตรวจ login และสิทธิ์
if "user_id" not in st.session_state or st.session_state.get("status") != "APPROVED":
    st.error("🚫 กรุณาเข้าสู่ระบบก่อนใช้งาน")
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
    #ปุ่มช่วยรีหน้าแบบต่างๆ
    col1, col2 = st.columns(2)

    with col1:
        if st.button("🔄 รีเฟรชหน้า", key="refresh_page"):
            st.rerun()

    with col2:
        if st.button("🆕 เริ่มแชทใหม่", key="reset_chat"):
            st.session_state["messages_gpt"] = []
            st.session_state["conversation_id"] = None
            st.session_state["last_saved_count"] = 0
            st.rerun()
#---------------
# ========== TAB 1: Chat with GPT ==========
if tab_choice == "💬 สนทนากับ GPT":
    st.subheader("🤖 สนทนากับ GPT (รองรับไฟล์ประกอบ)")
    st.caption("พิมพ์คำถามทั่วไป หรืออัปโหลดไฟล์เพื่อให้ช่วยวิเคราะห์")

    uploaded_file = st.file_uploader("📂 อัปโหลดไฟล์ (txt, csv, xlsx)", type=["txt", "csv", "xlsx"])

    if uploaded_file:
        try:
            file_bytes = uploaded_file.read()
            file_content = read_uploaded_file(uploaded_file.name, file_bytes)
            st.session_state["file_text"] = file_content
            st.text_area("📄 ตัวอย่างเนื้อหาไฟล์", file_content[:1000], height=200, disabled=True)
        except Exception as e:
            st.error(f"❌ ไม่สามารถอ่านไฟล์ได้: {e}")
            st.stop()

    file_content = st.session_state.get("file_text", "")
    st.session_state.setdefault("chat_all_in_one", [])

    # แสดงประวัติการสนทนา
    for msg in st.session_state["chat_all_in_one"]:
        st.chat_message(msg["role"]).write(msg["content"])

    if prompt := st.chat_input("พิมพ์คำถามของคุณ (หรือพิมพ์ว่า 'ขอไฟล์')"):
        st.chat_message("user").write(prompt)
        st.session_state["chat_all_in_one"].append({"role": "user", "content": prompt})

        if prompt.strip() == "ขอไฟล์" and st.session_state.get("analysis_result"):
            st.chat_message("assistant").write("📦 คลิกด้านล่างเพื่อดาวน์โหลดไฟล์ผลลัพธ์")
            st.session_state["show_download"] = True
        else:
            try:
                base_messages = [{"role": "system", "content": "คุณคือผู้ช่วยที่สามารถตอบคำถามทั่วไป และใช้เนื้อหาจากไฟล์หากมี"}]
                if file_content:
                    base_messages.append({"role": "user", "content": f"เนื้อหาในไฟล์:\n{file_content[:3000]}"})
                base_messages.append({"role": "user", "content": prompt})

                response = client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=base_messages
                )

                reply = response.choices[0].message.content
                usage = response.usage

                st.chat_message("assistant").write(reply)
                st.session_state["chat_all_in_one"].append({"role": "assistant", "content": reply})
                st.session_state["analysis_result"] = reply
                st.session_state["show_download"] = False

                st.session_state["messages_gpt"] = base_messages + [{
                    "role": "assistant",
                    "content": reply,
                    "prompt_tokens": usage.prompt_tokens,
                    "completion_tokens": usage.completion_tokens,
                    "total_tokens": usage.total_tokens
                }]

                save_conversation_if_ready(
                    conn, cursor, "messages_gpt", source="chat_gpt",
                    prompt_tokens=usage.prompt_tokens,
                    completion_tokens=usage.completion_tokens,
                    total_tokens=usage.total_tokens
                )

            except Exception as e:
                st.error(f"❌ Error: {e}")

    show_download_section()


# ========== Choice 2: เพิ่ม/เลือก Prompt ==========
elif tab_choice == "🧠 สนทนากับ Prompt":
    st.subheader("🧠 สนทนากับ Prompt")

    tab_chat, tab_manage = st.tabs([
        "💬 Prompt สำหรับแชททั่วไป",
        "✍️ บันทึก / จัดการ Prompt"
    ])

    # ===== TAB 1: 💬 Prompt สำหรับแชททั่วไป =====
    with tab_chat:
        st.caption("💬 ใช้ Prompt เพื่อคุยกับ GPT ในบริบทที่กำหนด เช่น นักบัญชี นักกฎหมาย ฯลฯ")

        prompts = list_prompts()
        prompt_dict = {name: content for name, content in prompts}

        if prompt_dict:
            selected_prompt_name = st.selectbox("🧠 เลือก Prompt", list(prompt_dict.keys()), key="prompt_selector")
            selected_prompt = prompt_dict[selected_prompt_name]

            with st.expander("📜 ข้อความ Prompt ที่เลือก"):
                st.code(selected_prompt)

            # 💬 ประวัติการสนทนา
            st.session_state.setdefault("chat_all_in_one", [])
            for msg in st.session_state["chat_all_in_one"]:
                st.chat_message(msg["role"]).write(msg["content"])

            # 💬 Input จากผู้ใช้
            if prompt := st.chat_input("พิมพ์คำถามของคุณ (หรือพิมพ์ว่า 'ขอไฟล์')"):
                st.chat_message("user").write(prompt)
                st.session_state["chat_all_in_one"].append({
                    "role": "user",
                    "content": prompt
                })

                if prompt.strip() == "ขอไฟล์" and st.session_state.get("analysis_result"):
                    st.chat_message("assistant").write("📦 คลิกด้านล่างเพื่อดาวน์โหลดไฟล์ผลลัพธ์")
                    st.session_state["show_download"] = True
                else:
                    try:
                        file_content = st.session_state.get("file_text", "")
                        base_messages = [
                            {"role": "system", "content": "คุณคือผู้ช่วยที่สามารถตอบคำถามทั่วไป และใช้เนื้อหาจากไฟล์หากมี"},
                            {"role": "user", "content": f"Prompt: {selected_prompt}"}
                        ]
                        if file_content:
                            base_messages.append({
                                "role": "user",
                                "content": f"เนื้อหาในไฟล์:\n{file_content[:3000]}"
                            })
                        base_messages.append({"role": "user", "content": prompt})

                        response = client.chat.completions.create(
                            model="gpt-3.5-turbo",
                            messages=base_messages
                        )
                        reply = response.choices[0].message.content
                        usage = response.usage

                        st.chat_message("assistant").write(reply)

                        st.session_state["chat_all_in_one"].append({
                            "role": "assistant", "content": reply
                        })
                        st.session_state["analysis_result"] = reply
                        st.session_state["show_download"] = False

                        # บันทึกประวัติการสนทนา
                        st.session_state["messages_gpt"] = base_messages + [{
                            "role": "assistant",
                            "content": reply,
                            "prompt_tokens": usage.prompt_tokens,
                            "completion_tokens": usage.completion_tokens,
                            "total_tokens": usage.total_tokens
                        }]

                        save_conversation_if_ready(
                            conn, cursor, "messages_gpt", "chat_gpt",
                            prompt_tokens=usage.prompt_tokens,
                            completion_tokens=usage.completion_tokens,
                            total_tokens=usage.total_tokens
                        )

                    except Exception as e:
                        st.error(f"❌ Error: {e}")

            # 📥 ปุ่มดาวน์โหลด (ถ้ามีการขอไฟล์)
            show_download_section()

        else:
            st.warning("⚠️ ยังไม่มี Prompt กรุณาเพิ่มที่แท็บ '✍️ บันทึก / จัดการ Prompt'")

    # ===== TAB 3: ✍️ บันทึก / จัดการ Prompt =====
    with tab_manage:
        st.caption("✍️ เพิ่ม ลบ หรือแก้ไข Prompt ที่ใช้ในระบบ")

        # ===== เพิ่ม Prompt ใหม่ =====
        prompt_name = st.text_input("📝 ตั้งชื่อ Prompt ใหม่", key="prompt_name_input_create")
        content = st.text_area("📄 เนื้อหา Prompt", height=120, key="prompt_content_input_create")
        if st.button("💾 บันทึก Prompt", key="save_prompt_create"):
            if prompt_name and content:
                save_prompt(prompt_name, content)
                st.success(f"✅ บันทึก Prompt “{prompt_name}” เรียบร้อยแล้ว")
                st.rerun()
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

                    with col2:
                        if st.button("🗑️ ลบ Prompt นี้", key=f"delete_prompt_{name}"):
                            delete_prompt(name)
                            st.success(f"✅ ลบแล้ว: {name}")
                            st.rerun()  # ✅ เช่นกัน
        else:
            st.info("ℹ️ ยังไม่มี Prompt ในระบบ")
               
# ========== Choice 3: History ==========
elif tab_choice == "📜 ประวัติการสนทนา":
    st.subheader("📜 ประวัติการสนทนา")
#=========== หน้ากรอก user id   ===========
    user_id = st.session_state.get("user_id")
    role = st.session_state.get("Role", "").lower()

    if role in ["admin", "super admin"]:
        convs = list_conversations()
    else:
        convs = list_conversations(user_id)
    if "messages_history" not in st.session_state:
        st.session_state["messages_history"] = []
#=========== หน้ากรอก user id   ===========
    label_map = {
    f"{name} ({created_at})": conv_id
    for conv_id, user_id, name, source, created_at in convs}
    selected = st.selectbox("📁 เลือกบทสนทนา", ["- เลือก -"] + list(label_map.keys()))

    if selected != "- เลือก -":
        conv_id = label_map[selected]
        cursor.execute("""
            SELECT role, content, prompt_tokens, completion_tokens, total_tokens
            FROM messages
            WHERE conversation_id = ?
            ORDER BY id
        """, (conv_id,))

        rows = cursor.fetchall()
        messages = []
        for r, c, p, comp, total in rows:
            messages.append({
                "role": r,
                "content": c,
                "prompt_tokens": p,
                "completion_tokens": comp,
                "total_tokens": total
            })
            
        if not st.session_state["messages_history"] or st.session_state.get("conv_id") != conv_id:
            st.session_state["messages_history"] = messages
            st.session_state["conv_id"] = conv_id

        for msg in st.session_state["messages_history"]:
            with st.chat_message(msg["role"]):
                st.markdown(msg["messages"])
                if msg["role"] == "assistant" and msg.get("total_tokens"):
                    st.caption(f"🔢 Tokens: total={msg['total_tokens']}, prompt={msg['prompt_tokens']}, completion={msg['completion_tokens']}")

        if prompt := st.chat_input("💬 พิมพ์ข้อความเพื่อต่อบทสนทนา", key="chat_continue_input"):
            st.chat_message("user").write(prompt)
            st.session_state["messages_history"].append({"role": "user", "messages": prompt})

            try:
                response = client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=st.session_state["messages_history"]
                )
                reply = response.choices[0].message.messages
                total_tokens = response.usage.total_tokens
            except Exception as e:
                reply = f"❌ Error: {e}"

            st.chat_message("assistant").write(reply)
            st.session_state["messages_history"].append({"role": "assistant", "content": reply})
            # ✅ Auto-save conversation
            save_conversation_if_ready(conn, cursor, "messages_history", "chat_history")
            
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

# ========== Choice 4 : วิธีการใช้งาน ==========
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

        ### อธิบายวิธีใช้ปุ่มด้านข้าง
        # ปุ่ม “🆕 เริ่มแชทใหม่”
        - ทุกแท็บมีปุ่มนี้ เพื่อเริ่มต้นสนทนาใหม่จากศูนย์
        - เหมาะเมื่อเปลี่ยนบริบทคำถาม หรือมีข้อมูลใหม่
        # ปุ่ม “🔄 รีเฟรชหน้า”
        - ทุกแท็บมีปุ่มนี้
        
        ---

        ### 📥 ดาวน์โหลดผลลัพธ์หลายรูปแบบ
        - สามารถเลือกบันทึกในฟอร์แมตต่าง ๆ:
        - `.txt` → ใช้ทั่วไป
        - `.md` → สำหรับ Markdown
        - `.csv` → เหมาะกับข้อมูลตาราง
        - `.xlsx` → สำหรับการเปิดใน Excel

        ---

        ### 💾 บันทึกบทสนทนาได้อัตโนมัติ!
        - สามารถดูย้อนหลังได้ในเมนู **📜 ประวัติการสนทนา**
        - แชทต่อจากเดิม หรืออัปเดตบทสนทนาเก่าได้

        ---
        """)
            
# Footer ด้านล่างสุด
st.markdown("""
    <hr style='margin-top: 3rem;'>
    <div style='text-align: center; color: gray;'>
        Provide ระบบสำหรับ วิลล่า มาร์เก็ตเจพี โดยยูนิคอร์น เทค อินทริเกรชั่น
    </div>
""", unsafe_allow_html=True)