# page/chat_with_ai.py
from utility_chat import *  # ทุกอย่างจากไฟล์ utility.py
from utility_ai import *

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
CHAT_TOKEN_VL = os.getenv("CHAT_TOKEN") or "Empty"  # Set ตัวแปร chat_token_vl

# ========== Role + User ==========
role = st.session_state.get("Role", "")
current_user = st.session_state.get("user_id", "")
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

st.page_link("app.py", label="⬅️ กลับหน้าหลัก", icon="🏠")
st.title("🤖 AI Chat Platform")
# ---------------
# ✅ ตรวจ login และสิทธิ์
if "user_id" not in st.session_state or st.session_state.get("status") != "APPROVED":
    st.error("🚫 กรุณาเข้าสู่ระบบก่อนใช้งาน")
    st.stop()
# ---------------
with st.sidebar:
    st.markdown("### 📑 เมนูหลัก")
    tab_choice = st.radio(
        "เลือกเมนู",
        ["💬 สนทนากับ GPT", "🧠 สนทนากับ Prompt", "📜 ประวัติการสนทนา", "📘 วิธีการใช้งาน"],
    )
    # ────────────────
    # 🛠 ปุ่มจัดการระบบ (ใน Sidebar)
    # ────────────────
    st.markdown("---")
    st.markdown("### 🛠 ควบคุมการสนทนา")

    # ✅ ปุ่มหยุดการทำงานของ AI
    if st.button("⛔ หยุดการทำงาน", key="stop_button_sidebar"):
        st.session_state["stop_chat"] = True
        st.warning("🛑 หยุดการทำงานของ AI แล้ว")

    # ✅ ปุ่มเริ่มต้นใหม่
    if st.button("🆕 เริ่มต้นบทสนทนาใหม่", key="reset_button_sidebar"):
        for key in [
            "chat_all_in_one",
            "messages_prompt",
            "analysis_result",
            "file_content",
            "conversation_title",
            "uploaded_filename",
            "tab_last",
            "model_last",
        ]:
            st.session_state.pop(key, None)
        st.rerun()
    # ======= ดู Token ที่ใช้แต่ละคน =======
    st.markdown("---")
    with st.expander("📊 Token ที่ใช้และคงเหลือของคุณ", expanded=False):
        from utility_chat import init_db

        conn, cursor = init_db()

        # 🔄 ดึงรวม token ที่ใช้ต่อ user
        cursor.execute(
            """
            SELECT user_id, SUM(total_tokens) as total
            FROM token_usage
            GROUP BY user_id
            """
        )
        rows = cursor.fetchall()
        df = pd.DataFrame(rows, columns=["user_id", "รวม Token ที่ใช้"])

        # 🧠 ระบุผู้ใช้งานปัจจุบัน
        current_user = st.session_state.get("user_id", "")

        # 🔍 ดึง quota override ล่าสุดจาก DB สำหรับ user นี้
        cursor.execute(
            """
            SELECT quota_override FROM token_usage
            WHERE user_id = ?
            AND quota_override IS NOT NULL
            ORDER BY id DESC LIMIT 1
            """,
            (current_user,),
        )
        quota_row = cursor.fetchone()
        current_quota = (
            quota_row[0] if quota_row else 1_000_000
        )  # fallback ถ้าไม่มี quota_override

        # ✅ กรองเฉพาะข้อมูลของ user นี้
        df = df[df["user_id"] == current_user]

        if df.empty:
            # 🧾 ถ้าไม่มี record token usage มาก่อน
            df = pd.DataFrame(
                [
                    {
                        "user_id": current_user,
                        "รวม Token ที่ใช้": 0,
                    }
                ]
            )

        # ✅ คำนวณข้อมูลที่เหลือ
        df["โควตา Token"] = current_quota
        df["Token คงเหลือ"] = df["โควตา Token"] - df["รวม Token ที่ใช้"]
        df["% ที่ใช้แล้ว"] = (df["รวม Token ที่ใช้"] / df["โควตา Token"] * 100).round(2)

        # ✅ แสดงผลแบบรายบรรทัด
        for _, row in df.iterrows():
            st.markdown(
                f"""
                👤 `User ID`: `{row["user_id"]}`  
                🔢 **รวม Token ที่ใช้**: `{row["รวม Token ที่ใช้"]:,}`  
                🎯 **โควตา Token**: `{row["โควตา Token"]:,}`  
                ✅ **Token คงเหลือ**: `{row["Token คงเหลือ"]:,}`  
                📈 ใช้ไปแล้ว: `{row["% ที่ใช้แล้ว"]}%`  
                ---
                """
            )


# TODO เลือกโมเดล (เฉพาะในแชท)
# ==== ดึงรายชื่อโมเดลจาก Ollama ====
ollama_models = (
    get_ollama_models())  # ควร return เป็น list เช่น ["gemma3:12b", "DSV2:16b"]
gpt_models = ["gpt-4o"]
chat_all_in_one = gpt_models + ollama_models

# ==== ตั้ง default model ครั้งแรก ====
if "default_model" not in st.session_state:
    # ตั้ง gpt-4o ถ้าไม่มี Ollama หรือเลือกตัวแรกจาก Ollama
    st.session_state["default_model"] = ollama_models[0] if ollama_models else "gpt-4o"

# ==== ให้ผู้ใช้เลือกโมเดลเริ่มต้นแบบซ่อน UI ====
with st.expander("⚙️ ตั้งค่าโมเดลเริ่มต้น (ผู้ดูแลระบบ)"):
    try:
        default_model = st.selectbox(
            "🧠 เลือกโมเดลเริ่มต้นที่ต้องการใช้งานจริง",
            chat_all_in_one,
            index=chat_all_in_one.index(st.session_state["default_model"]),
            key="default_model_selector",
        )
    except ValueError:
        default_model = "gpt-4o"

    st.session_state["default_model"] = default_model

# ===== ใช้งานจริง =====
model_choice = st.session_state["default_model"]

st.markdown(f"✅ **โมเดลที่ใช้งานขณะนี้:** `{model_choice}`", unsafe_allow_html=True)

# ตรวจจับการเปลี่ยนแท็บ
reset_tab(tab_choice, model_choice)
reset_on_button_click()
# ---------------
# อ่านจำนวน token ที่ใช้แล้วจากฐานข้อมูล
cursor.execute(
    """
    SELECT SUM(total_tokens) FROM token_usage WHERE user_id = ?
""",
    (current_user,),
)
row = cursor.fetchone()
used_token = row[0] or 0  # หากยังไม่เคยใช้เลย row[0] จะเป็น None

check_token_quota()
# ========== TAB 1: Chat with GPT ==========
if tab_choice == "💬 สนทนากับ GPT":
    st.subheader("🤖 สนทนากับ GPT (รองรับไฟล์ประกอบ)")
    st.caption("พิมพ์คำถามทั่วไป หรืออัปโหลดไฟล์เพื่อให้ช่วยวิเคราะห์")

    with st.expander("📂 ขยายเพื่ออัปโหลดไฟล์ (txt, csv, xlsx)", expanded=False):
        uploaded_file = st.file_uploader("📂 อัปโหลดไฟล์ (txt, csv, xlsx)", 
                                         type=["txt", "csv", "xlsx"],
                                         accept_multiple_files=True)

    if uploaded_file:
        all_content = ""
        for uploaded_file in uploaded_file:
            try:
                file_content = read_uploaded_file(uploaded_file.name, uploaded_file)
                all_content += f"\n\n### {uploaded_file.name}\n{file_content}"

                st.text_area(
                    f"📄 ตัวอย่างจาก {uploaded_file.name}",
                    file_content[:1000],
                    height=200,
                    disabled=True,
                )
                st.session_state[f"file_{uploaded_file.name}"] = file_content

            except Exception as e:
                st.error(f"❌ ไม่สามารถอ่านไฟล์ {uploaded_file.name} ได้: {e}")

        # ✅ บันทึกรวมไฟล์ไว้ใช้งานร่วมกับ AI
        st.session_state["file_text"] = all_content

    # ค่าเริ่มต้น
    file_content = st.session_state.get("file_text", "")
    st.session_state.setdefault("chat_all_in_one", [])

    # แสดงบทสนทนาย้อนหลัง
    for msg in st.session_state["chat_all_in_one"]:
        st.chat_message(msg["role"]).write(msg["content"])

    # ช่องพิมพ์คำถาม
    if prompt := st.chat_input("พิมพ์คำถามของคุณ (หรือพิมพ์ว่า 'ขอไฟล์')"):
        token_fn = count_tokens if model_choice.startswith("gpt-") else estimate_tokens

        # เพิ่มข้อความของผู้ใช้พร้อม token_count
        st.chat_message("user").write(prompt)
        st.session_state["chat_all_in_one"].append(
            {
                "role": "user",
                "content": prompt,
                # "token_count": token_fn(prompt, model_choice),
            }
        )

        # คำสั่งขอไฟล์
        if prompt.strip() == "ขอไฟล์":
            if not st.session_state.get("analysis_result"):
                st.chat_message("assistant").write("⚠️ ยังไม่มีผลลัพธ์ให้ดาวน์โหลด กรุณาถามคำถามก่อน")
            else:
                st.chat_message("assistant").write("📦 คลิกเพื่อดาวน์โหลดผลลัพธ์ที่ได้จาก AI")
                st.session_state["show_download"] = True

        else:
            try:
                # สร้าง prompt เต็ม
                base_messages = [
                    {
                        "role": "system",
                        "content": "คุณคือผู้ช่วยที่สามารถตอบคำถามทั่วไป และใช้เนื้อหาจากไฟล์หากมี",
                    }
                ]
                if file_content:
                    base_messages.append(
                        {"role": "user", "content": f"เนื้อหาในไฟล์ทั้งหมด:\n{file_content}"}
                    )
                base_messages.extend(st.session_state["chat_all_in_one"])

                with st.chat_message("assistant"):
                    stream_output = st.empty()
                    result = display_ai_response_info(
                        model_choice, base_messages, stream_output
                    )

                # เพิ่มข้อความตอบกลับเข้า history
                st.session_state["chat_all_in_one"].append(
                    {
                        "role": "assistant",
                        "content": result["reply"],
                        "prompt_tokens": result["prompt_tokens"],
                        "completion_tokens": result["completion_tokens"],
                        "total_tokens": result["total_tokens"],
                        "response_json": result["response_json"],
                    }
                )

                # สำหรับแสดงผล / ดาวน์โหลด
                st.session_state["analysis_result"] = result["reply"]
                st.session_state["show_download"] = False

                # เตรียมสำหรับ save DB
                st.session_state["messages_gpt"] = base_messages + [
                    {
                        "role": "assistant",
                        "content": result["reply"],
                        "prompt_tokens": result["prompt_tokens"],
                        "completion_tokens": result["completion_tokens"],
                        "total_tokens": result["total_tokens"],
                        "response_json": result["response_json"],
                    }
                ]

                # บันทึกลง SQLite
                save_conversation_if_ready(
                    conn,
                    cursor,
                    messages_key="messages_gpt",         # ✅ ต้องใส่ค่าให้ชัดเจน
                    source=model_choice,                 # เช่น "gpt-4o" หรือ "llama2:latest"
                    prompt_tokens=result["prompt_tokens"],
                    completion_tokens=result["completion_tokens"],
                    total_tokens=result["total_tokens"],
                )

                if "conversation_title" not in st.session_state:
                    from utility_ai import generate_title_from_conversation

                    title = generate_title_from_conversation(
                        st.session_state["messages_gpt"]
                    )
                    st.session_state["conversation_title"] = title  # ใช้ใน UI
                    save_conversation_if_ready(
                        cursor, title
                    )  # ต้องสร้างฟังก์ชันนี้ให้เขียนเข้า DB
                    conn.commit()

            except Exception as e:
                st.error(f"❌ Error: {e}")

    # ปุ่มดาวน์โหลดผลลัพธ์
    show_download_section()

# ========== Choice 2: เพิ่ม/เลือก Prompt ==========
elif tab_choice == "🧠 สนทนากับ Prompt":
    st.subheader("🧠 สนทนากับ Prompt")

    tab_chat, tab_manage = st.tabs(["💬 Prompt สำหรับแชททั่วไป", "✍️ บันทึก / จัดการ Prompt"])

    with tab_chat:
        st.caption("ใช้ Prompt เพื่อคุยกับ GPT ในบริบทที่กำหนด เช่น นักบัญชี นักกฎหมาย")

        prompts = list_prompts()
        prompt_dict = {name: content for name, content in prompts}

        if prompt_dict:
            selected_prompt_name = st.selectbox(
                "เลือก Prompt", list(prompt_dict.keys()), key="prompt_selector"
            )
            selected_prompt = prompt_dict[selected_prompt_name]

            with st.expander("ข้อความ Prompt ที่เลือก"):
                st.code(selected_prompt)

            st.session_state.setdefault("chat_all_in_one", [])
            st.session_state.setdefault("messages_prompt", [])
            st.session_state.setdefault("messages_gpt", [])

            for msg in st.session_state["chat_all_in_one"]:
                st.chat_message(msg["role"]).write(msg["content"])

            with st.expander("📂 อัปโหลดไฟล์ (ไม่บังคับ)", expanded=False):
                uploaded_files = st.file_uploader(
                    "อัปโหลดไฟล์ (.txt, .csv, .xlsx) เพื่อใช้ร่วมกับ Prompt (ถ้ามี)",
                    type=["txt", "csv", "xlsx"],
                    accept_multiple_files=True,
                )

            file_content_all = ""
            if uploaded_files:
                st.session_state["uploaded_filename"] = [f.name for f in uploaded_files]
                st.session_state["analysis_results"] = []
                for uploaded_file in uploaded_files:
                    try:
                        content = read_uploaded_file(uploaded_file.name, uploaded_file)
                        file_content_all += (
                            f"\n\n### ไฟล์: {uploaded_file.name}\n{content}"
                        )
                        st.text_area(
                            f"📄 ตัวอย่างจาก {uploaded_file.name}",
                            content[:3000],
                            height=200,
                            disabled=True,
                        )
                        st.session_state[f"file_{uploaded_file.name}"] = content
                    except Exception as e:
                        st.error(f"❌ ไม่สามารถอ่านไฟล์ {uploaded_file.name} ได้: {e}")

                st.session_state["file_content"] = file_content_all

                if st.button("🔍 วิเคราะห์ไฟล์ด้วย Prompt ที่เลือก"):
                    file_content = st.session_state.get("file_content", "")
                    prompt_input = f"คำสั่ง:{selected_prompt} เนื้อหาไฟล์:{file_content}"

                    base_messages = [
                        {"role": "system", "content": selected_prompt},
                        {"role": "user", "content": prompt_input},
                    ]

                    with st.chat_message("assistant"):
                        stream_output = st.empty()
                        result = display_ai_response_info(
                            model_choice, base_messages, stream_output
                        )

                    reply = result["reply"]
                    raw_json = result["response_json"]

                    st.session_state["chat_all_in_one"].append(
                        {"role": "assistant", "content": reply}
                    )
                    st.session_state["analysis_result"] = reply
                    st.session_state["show_download"] = False

                    st.session_state["messages_prompt"] = base_messages + [
                        {
                            "role": "assistant",
                            "content": reply,
                            "prompt_tokens": result["prompt_tokens"],
                            "completion_tokens": result["completion_tokens"],
                            "total_tokens": result["total_tokens"],
                            "response_json": raw_json,
                        }
                    ]

                    save_conversation_if_ready(
                        conn,
                        cursor,
                        messages_key="messages_prompt",
                        source=model_choice,
                        prompt_tokens=result["prompt_tokens"],
                        completion_tokens=result["completion_tokens"],
                        total_tokens=result["total_tokens"],
                    )

            # ✅ พร้อมแชทต่อ
            if prompt := st.chat_input("พิมพ์คำถามของคุณ (หรือพิมพ์ว่า 'ขอไฟล์')"):
                st.chat_message("user").write(prompt)
                st.session_state["chat_all_in_one"].append(
                    {"role": "user", "content": prompt}
                )

                file_content = st.session_state.get("file_content", "")
                prompt_input = f"คำสั่ง:{selected_prompt} คำถามเพิ่มเติม:{prompt}"

                base_messages = [
                    {"role": "system", "content": selected_prompt},
                    {"role": "user", "content": prompt_input},
                ]

                with st.chat_message("assistant"):
                    stream_output = st.empty()
                    result = display_ai_response_info(
                        model_choice, base_messages, stream_output
                    )

                reply = result["reply"]
                raw_json = result["response_json"]

                st.session_state["chat_all_in_one"].append(
                    {"role": "assistant", "content": reply}
                )
                st.session_state["analysis_result"] = reply
                st.session_state["show_download"] = False

                st.session_state["messages_prompt"] = base_messages + [
                    {
                        "role": "assistant",
                        "content": reply,
                        "prompt_tokens": result["prompt_tokens"],
                        "completion_tokens": result["completion_tokens"],
                        "total_tokens": result["total_tokens"],
                        "response_json": raw_json,
                    }
                ]

                save_conversation_if_ready(
                    conn,
                    cursor,
                    messages_key="messages_prompt",
                    source=model_choice,
                    prompt_tokens=result["prompt_tokens"],
                    completion_tokens=result["completion_tokens"],
                    total_tokens=result["total_tokens"],
                )

                show_download_section()

        else:
            st.warning("⚠️ ยังไม่มี Prompt กรุณาเพิ่มที่แท็บ '✨ บันทึก / จัดการ Prompt'")

    # ===== TAB 2: ✍️ บันทึก / จัดการ Prompt =====
    with tab_manage:
        st.caption("✍️ เพิ่ม ลบ หรือแก้ไข Prompt ที่ใช้ในระบบ")

        # ===== เพิ่ม Prompt ใหม่ =====
        prompt_name = st.text_input(
            "📝 ตั้งชื่อ Prompt ใหม่", key="prompt_name_input_create"
        )
        content = st.text_area(
            "📄 เนื้อหา Prompt", height=120, key="content_input_create"
        )
        if st.button("💾 บันทึก Prompt", key="save_prompt_create"):
            if prompt_name and content:
                save_prompt(prompt_name, content)
                st.success(f"✅ บันทึก Prompt “{prompt_name}” เรียบร้อยแล้ว")
                st.toast("✅ ดำเนินการเสร็จสิ้น", icon="✅")
                st.rerun()
            else:
                st.warning("⚠️ กรุณากรอกชื่อและเนื้อหา Prompt")

        # ===== รายการ Prompt ที่มี พร้อมแก้ไข/ลบ =====
        prompts = list_prompts()
        if prompts:
            st.markdown("### 🗂 รายการ Prompt ที่มี")
            for name, content in prompts:
                with st.expander(f"📌 {name}", expanded=False):
                    edited_content = st.text_area(
                        "🔧 แก้ไขเนื้อหา Prompt",
                        value=content,
                        height=150,
                        key=f"edit_{name}",
                    )

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
    # =========== หน้ากรอก user id   ===========
    user_id = st.session_state.get("user_id")
    role = st.session_state.get("Role", "").lower()

    if role in ["admin", "super admin"]:
        convs_all = list_conversations()
    else:
        convs_all = list_conversations(user_id)

    # ===== เพิ่ม filter ตามโมเดล =====
    st.sidebar.markdown("### 🎛️ ตัวกรอง")
    model_filter = st.sidebar.selectbox(
        "📦 แสดงบทสนทนาที่ใช้โมเดล", ["ทั้งหมด"] + sorted(list(set(c[3] for c in convs_all)))
    )

    if model_filter != "ทั้งหมด":
        convs = [c for c in convs_all if c[3] == model_filter]
    else:
        convs = convs_all

    if "messages_history" not in st.session_state:
        st.session_state["messages_history"] = []

    label_map = {
        f"{name} [{source}] ({created_at})": conv_id
        for conv_id, user_id, name, source, prompt_tokens, completion_tokens, total_tokens, created_at in convs
    }
    selected = st.selectbox("📁 เลือกบทสนทนา", ["- เลือก -"] + list(label_map.keys()))

    if selected != "- เลือก -":
        conv_id = label_map[selected]

        # ===== แสดงชื่อบทสนทนาและแก้ไขชื่อ =====
        title = selected.split(" [")[0]
        st.markdown(f"### 🗂️ หัวข้อ: `{title}`")

        new_title = st.text_input(
            "✏️ เปลี่ยนชื่อบทสนทนา", value=title, key="rename_title_input"
        )
        if new_title.strip() != title:
            cursor.execute(
                "UPDATE conversations SET title = ? WHERE id = ?",
                (new_title.strip(), conv_id),
            )
            conn.commit()
            st.success("✅ เปลี่ยนชื่อหัวข้อเรียบร้อยแล้ว")
            st.rerun()

        cursor.execute(
            """
            SELECT role, content, prompt_tokens, completion_tokens, total_tokens
            FROM messages
            WHERE conversation_id = ?
            ORDER BY id
            """,
            (conv_id,),
        )
        rows = cursor.fetchall()
        messages = [
            {
                "role": r,
                "content": c,
                "prompt_tokens": p,
                "completion_tokens": comp,
                "total_tokens": total,
            }
            for r, c, p, comp, total in rows
        ]

        if (
            not st.session_state.get("messages_history")
            or st.session_state.get("conv_id") != conv_id
        ):
            st.session_state["messages_history"] = messages
            st.session_state["conv_id"] = conv_id

        MAX_CHARS = 300
        PREVIEW_CHARS = 50  # จำนวนตัวอักษรที่แสดงเป็น preview

        for msg in st.session_state.get("messages_history", []):
            role = msg.get("role", "user")
            content = msg.get("content", "").strip()

            with st.chat_message(role):
                if len(content) > MAX_CHARS:
                    preview = content[:PREVIEW_CHARS].rsplit(" ", 1)[0] + "..."  # ตัดให้จบที่คำ
                    st.markdown(preview)  # แสดง preview ด้านนอก

                    with st.expander("📄 ดูข้อความทั้งหมด"):
                        st.markdown(content)
                else:
                    st.markdown(content)

                if role == "assistant" and msg.get("total_tokens"):
                    st.caption(
                        f"🔢 Tokens: total={msg.get('total_tokens', 0)}, "
                        f"prompt={msg.get('prompt_tokens', 0)}, "
                        f"completion={msg.get('completion_tokens', 0)}"
                    )
        if prompt := st.chat_input(
            "💬 พิมพ์ข้อความเพื่อต่อบทสนทนา", key="chat_continue_input"
        ):
            st.chat_message("user").write(prompt)
            st.session_state["messages_history"].append(
                {"role": "user", "content": prompt}
            )

            try:
                with st.chat_message("assistant"):
                    stream_output = st.empty()
                    result = stream_response_by_model(
                        model_choice,
                        st.session_state["messages_history"],
                        stream_output,
                    )
                    reply = result["reply"]
                    stream_output.markdown(reply)

                st.session_state["messages_history"].append(
                    {
                        "role": "assistant",
                        "content": reply,
                        "prompt_tokens": result["prompt_tokens"],
                        "completion_tokens": result["completion_tokens"],
                        "total_tokens": result["total_tokens"],
                        "response_json": result["response_json"],
                    }
                )

                save_conversation_if_ready(
                    conn,
                    cursor,
                    messages_key="messages_history",
                    source=model_choice,
                    prompt_tokens=result["prompt_tokens"],
                    completion_tokens=result["completion_tokens"],
                    total_tokens=result["total_tokens"],
                )

            except Exception as e:
                st.error(f"❌ Error: {e}")

        with st.expander("🗑️ ลบบทสนทนานี้"):
            if st.button("ยืนยันการลบ", key="confirm_delete_conv"):
                cursor.execute(
                    "DELETE FROM messages WHERE conversation_id = ?", (conv_id,)
                )
                cursor.execute("DELETE FROM conversations WHERE id = ?", (conv_id,))
                conn.commit()

                reset_on_button_click()
                st.success("✅ ลบบทสนทนาเรียบร้อยแล้ว")
                st.rerun()

        if st.session_state.get("messages_history"):
            with st.expander("📅 ดาวน์โหลดบทสนทนาเป็นไฟล์"):
                file_format = st.selectbox(
                    "📄 เลือกรูปแบบไฟล์",
                    ["txt", "md", "json", "csv"],
                    key="history_download_format",
                )
                file_name = st.text_input(
                    "📝 ตั้งชื่อไฟล์", value="chat_history", key="history_download_filename"
                )

                full_filename = f"{file_name.strip()}.{file_format}"
                mime_type = "text/plain"
                content_lines = []
                file_bytes = StringIO()
                history = st.session_state["messages_history"]

                if file_format in ["txt", "md"]:
                    for msg in history:
                        role = msg.get("role", "unknown").capitalize()
                        text = msg.get("content", "").strip()
                        if not text:
                            continue
                        content_lines.append(
                            f"**{role}:**\n{text}\n"
                            if file_format == "md"
                            else f"{role}:\n{text}\n"
                        )
                        mime_type = (
                            "text/markdown" if file_format == "md" else "text/plain"
                        )
                    file_bytes.write("\n".join(content_lines))

                elif file_format == "json":
                    file_bytes.write(json.dumps(history, ensure_ascii=False, indent=2))
                    mime_type = "application/json"

                elif file_format == "csv":
                    pd.DataFrame(history).to_csv(
                        file_bytes, index=False, encoding="utf-8-sig"
                    )
                    mime_type = "text/csv"

                file_bytes.seek(0)
                st.download_button(
                    label="⬇️ ดาวน์โหลดไฟล์",
                    data=file_bytes.getvalue(),
                    file_name=full_filename,
                    mime=mime_type,
                )

# ========== Choice 4 : วิธีการใช้งาน ==========
if tab_choice == "📘 วิธีการใช้งาน":
    st.subheader("📘 วิธีการใช้งานโปรแกรม")
    tab_intro, tab_howto, tab_tip = st.tabs(
        ["🧩 คุณสมบัติของโปรแกรม", "💡 วิธีใช้งาน Chatai", "💡 เคล็ดลับเพิ่มเติม"]
    )

    with tab_intro:
        st.subheader("🧩 คุณสมบัติของโปรแกรม")
        st.markdown(
            """
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
        """
        )

    with tab_howto:
        st.subheader("📝 วิธีใช้งานแต่ละเมนู")
        st.markdown(
            """
        Chatai ถูกออกแบบให้ใช้งานง่ายผ่าน 4 เมนูหลักทางด้านซ้ายของหน้าจอ โดยสามารถทำงานร่วมกับ GPT-3.5/4 และเอกสารต่าง ๆ ได้ทันที

        ### 1️⃣  💬 สนทนากับ GPT
        - วิเคราะห์ไฟล์เอกสาร (📄 คุยกับไฟล์)
        - เหมาะสำหรับถามตอบทั่วไป
        - สามารถเริ่มสนทนาใหม่ได้ทุกครั้งด้วยปุ่ม **"🆕 เริ่มแชทใหม่"**
        - พิมพ์คำถามในกล่องด้านล่าง แล้วรอรับคำตอบจาก GPT
        - สามารถบันทึกบทสนทนาไว้ใช้งานภายหลังได้ด้วยปุ่ม **"💾 บันทึกบทสนทนา"**
        ---
        ### 2️⃣ ใช้ Prompt เฉพาะทาง (🧠 เพิ่ม/เลือก Prompt)
        - สร้าง Prompt พิเศษเพื่อกำหนดบทบาทหรือบริบทของ GPT (เช่น นักบัญชี, นักกฎหมาย, ที่ปรึกษา ฯลฯ)
        - เลือก Prompt ที่ต้องการ แล้วเริ่มสนทนาในบริบทนั้นได้ทันที
        - แนบไฟล์เพื่อให้ GPT วิเคราะห์ร่วมกับ Prompt ก็ได้
        - สามารถลบหรือแก้ไข Prompt ได้ภายหลัง
        ---
        ###3️⃣ ประวัติการสนทนา (📜 แชทต่อจากบทสนทนาเดิม)
        - ดูบทสนทนาเดิมทั้งหมดที่เคยบันทึกไว้
        - เลือกบทสนทนา > แชทต่อจากจุดเดิมได้เลย
        - สามารถอัปเดต/แก้ไขบทสนทนาเดิมและบันทึกซ้ำได้
        - **มีปุ่มลบประวัติ** สำหรับบทสนทนาที่ไม่ต้องการเก็บไว้
        ---
        💡 **แนะนำ:** ทุกการใช้งานสามารถใช้ได้ฟรีผ่าน GPT-3.5 หรือเปลี่ยนเป็น GPT-4 (ถ้ามี API Key ที่รองรับ)
        """
        )
        with tab_tip:
            st.markdown(
                """
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
        ---
        ### 🆕 เริ่มแชทใหม่
        - ล้างข้อมูลทั้งหมด เช่น ประวัติแชท, ไฟล์ที่อัปโหลด, ผลวิเคราะห์
        - เหมาะสำหรับ: เริ่มต้นหัวข้อใหม่, เปลี่ยนไฟล์ใหม่
        - การทำงาน: เคลียร์ st.session_state และ rerun
        ---
        ###🔄 รีเฟรชหน้า
        - โหลดหน้าใหม่ โดย ไม่ล้างข้อมูลเดิม
        - เหมาะสำหรับ: อัปเดต UI หรือแก้ปัญหาการแสดงผล
        - การทำงาน: เรียก st.experimental_rerun() เฉย ๆ
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
        """
            )

# Footer ด้านล่างสุด
st.markdown(
    """
    <hr style='margin-top: 3rem;'>
    <div style='text-align: center; color: gray;'>
        Provide ระบบสำหรับ วิลล่า มาร์เก็ตเจพี โดยยูนิคอร์น เทค อินทริเกรชั่น
    </div>
""",
    unsafe_allow_html=True,
)
