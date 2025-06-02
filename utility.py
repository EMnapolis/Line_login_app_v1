import streamlit as st
import os
import sqlite3
import pandas as pd
from io import BytesIO
from openai import OpenAI
from datetime import datetime
from langchain.chat_models import ChatOpenAI
from langchain.document_loaders import TextLoader
from langchain.vectorstores import Chroma
from langchain.chains import ConversationalRetrievalChain
from langchain.memory import ConversationBufferMemory
from langchain.embeddings.openai import OpenAIEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.docstore.document import Document
from charset_normalizer import from_bytes
from dotenv import load_dotenv
import tiktoken

#==== global path ====
db_path = os.path.join("data", "sqdata.db")
schema_path = os.path.join("data", "schema.sql")
user_id = st.session_state.get("user_id")
#==== global path ====

# ✅ โหลดจาก config.py แทนการใช้ os.getenv() เอง
from config import OPENAI_API_KEY, CHAT_TOKEN

# ===== OpenAI Client =====
client = OpenAI(api_key=OPENAI_API_KEY)

# ===== เชื่อมต่อฐานข้อมูล SQLite =====
def init_db():
    first_time = not os.path.exists(db_path)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    cursor = conn.cursor()
    if first_time:
        initialize_schema(conn)
    return conn, cursor

# ===== โหลด schema.sql และรันเพื่อสร้างตาราง =====
def initialize_schema(conn):
    if not os.path.exists(schema_path):
        raise FileNotFoundError(f"❌ ไม่พบไฟล์: {schema_path}")
    with open(schema_path, "r", encoding="utf-8") as f:
        sql_script = f.read()
    conn.executescript(sql_script)
    conn.commit()

# ===== บันทึกบทสนทนาลงฐานข้อมูล =====
def save_conversation_if_ready(conn, cursor, messages_key, source="chat_gpt"):
    messages = st.session_state.get(messages_key, [])
    conv_key = f"conversation_id_{messages_key}"
    last_key = f"last_saved_count_{messages_key}"

    conv_id = st.session_state.get(conv_key)
    last_saved_count = st.session_state.get(last_key, 0)

    if len(messages) >= 2 and len(messages) > last_saved_count:
        last_two = messages[-2:]
        if last_two[0]["role"] == "user" and last_two[1]["role"] == "assistant":
            title = generate_title_from_conversation(messages)

            # ➕ สร้าง conversation ถ้ายังไม่มี
            if conv_id is None:
                cursor.execute("""
                    INSERT INTO conversations (user_id, name, source)
                    VALUES (?, ?, ?)
                """, (st.session_state["user_id"], title, source))
                conv_id = cursor.lastrowid
                st.session_state[conv_key] = conv_id

            # ➕ เพิ่มข้อความใหม่
            for msg in messages[last_saved_count:]:
                cursor.execute("""
                    INSERT INTO messages (user_id, conversation_id, role, content, total_tokens)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    st.session_state["user_id"],
                    conv_id,
                    msg.get("role", "user"),
                    msg.get("content", ""),
                    msg.get("total_tokens", "")
                ))

            conn.commit()
            st.session_state[last_key] = len(messages)
            st.toast(f"💾 บันทึกบทสนทนาใหม่จาก {source}")

# ===== token count ====
def count_tokens(messages, model="gpt-3.5-turbo"):
    enc = tiktoken.encoding_for_model(model)
    total = 0
    for msg in messages:
        content = msg.get("content", "")
        total += len(enc.encode(content))
    return total

# ===== ใช้ AI ตั้งชื่อบทสนทนาแบบย่อ =====
def generate_title_from_conversation(messages):
    try:
        system_prompt = {"role": "system", "content": "You are an assistant that summarizes the topic of a conversation in 5-10 Thai words."}
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[system_prompt] + messages + [{"role": "user", "content": "สรุปชื่อหัวข้อของบทสนทนานี้สั้น ๆ"}]
        )
        return response.choices[0].message.content.strip()
    except Exception:
        return "บทสนทนาใหม่" if not messages else messages[0].get("content", "บทสนทนาใหม่")[:30]

# ===== ดึงรายชื่อบทสนทนา =====
def list_conversations(user_id=None):
    db_path = os.path.join("data", "sqdata.db")
    conn = sqlite3.connect(db_path, check_same_thread=False)

    query = "SELECT id, user_id, name, source, created_at FROM conversations"
    params = ()

    if user_id:
        query += " WHERE user_id = ?"
        params = (user_id,)

    query += " ORDER BY created_at DESC"
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    return df.values.tolist()

# ===== จัดการตาราง Prompt =====
def init_prompt_table():
    conn = sqlite3.connect(db_path, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS prompts (
            name TEXT PRIMARY KEY,
            content TEXT
        )
    """)
    conn.commit()
def save_prompt(name, content):
    user_id = st.session_state.get("user_id")
    if not user_id:
        st.warning("⛔ กรุณาเข้าสู่ระบบ")
        return
    conn = sqlite3.connect(db_path, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("""
        REPLACE INTO prompts (name, user_id, content)
        VALUES (?, ?, ?)
    """, (name, user_id, content))
    conn.commit()
    conn.close()
def list_prompts():
    user_id = st.session_state.get("user_id")
    role = st.session_state.get("Role", "user")

    conn = sqlite3.connect(db_path, check_same_thread=False)
    cursor = conn.cursor()

    if role == "admin":
        cursor.execute("SELECT name, content FROM prompts ORDER BY name")
    else:
        cursor.execute("SELECT name, content FROM prompts WHERE user_id = ? ORDER BY name", (user_id,))

    results = cursor.fetchall()
    conn.close()
    return results
def delete_prompt(name):
    user_id = st.session_state.get("user_id")
    role = st.session_state.get("Role", "user")

    conn = sqlite3.connect(db_path, check_same_thread=False)
    cursor = conn.cursor()

    if role == "admin":
        cursor.execute("DELETE FROM prompts WHERE name = ?", (name,))
    else:
        cursor.execute("DELETE FROM prompts WHERE name = ? AND user_id = ?", (name, user_id))

    conn.commit()
    conn.close()

# ===== 📂 การอัปโหลดไฟล์และสร้างเวกเตอร์ =====
def process_file_to_chain(uploaded_file):
    """แปลงไฟล์เป็นเวกเตอร์ และสร้าง Conversational RAG Chain เพื่อถามตอบจากเนื้อหาไฟล์"""
    if not uploaded_file:
        st.warning("⚠️ กรุณาอัปโหลดไฟล์ก่อน")
        return

    with st.spinner("🔄 กำลังแปลงและฝังเวกเตอร์จากไฟล์..."):
        try:
            file_bytes = uploaded_file.read()

            # 🔍 ตรวจ encoding และ decode ไฟล์
            file_content = try_decode_file(file_bytes)

            # 📝 Preview ตัวอย่างเนื้อหา
            st.text_area("📖 ตัวอย่างเนื้อหาในไฟล์", file_content[:1000], height=200, disabled=True)

            # 🔹 แบ่งข้อความเป็น chunks
            docs = [Document(page_content=file_content)]
            splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
            split_docs = splitter.split_documents(docs)

            # 🧬 แปลงเป็นเวกเตอร์
            embeddings = OpenAIEmbeddings(openai_api_key=OPENAI_API_KEY)
            vectorstore = Chroma.from_documents(split_docs, embeddings)

            # 🔁 สร้าง RAG Chain สำหรับโต้ตอบ
            chain = ConversationalRetrievalChain.from_llm(
                llm=ChatOpenAI(temperature=0, openai_api_key=OPENAI_API_KEY),
                retriever=vectorstore.as_retriever(),
                memory=ConversationBufferMemory(memory_key="chat_history", return_messages=True),
            )

            # 💾 เก็บลง session
            st.session_state["chain"] = chain
            st.session_state["chat_history"] = []
            st.session_state["file_content"] = file_content

            st.success("✅ ประมวลผลเสร็จแล้ว! พิมพ์คำถามเกี่ยวกับเนื้อหาไฟล์ได้เลย")

        except Exception as e:
            st.error(f"❌ เกิดข้อผิดพลาด: {e}")

# ===== 🔍 ฟังก์ชันตรวจสอบและแปลง encoding ของไฟล์ =====
def try_decode_file(file_bytes: bytes) -> str:
    """พยายาม decode ไฟล์โดยใช้ charset_normalizer และ fallback encoding"""
    try:
        from charset_normalizer import from_bytes
        result = from_bytes(file_bytes).best()
        if result:
            return str(result)
    except Exception:
        pass

    # Fallback แบบแมนนวล
    try:
        return file_bytes.decode("utf-8")
    except UnicodeDecodeError:
        try:
            return file_bytes.decode("iso-8859-1")
        except Exception as e:
            raise ValueError(f"❌ ไม่สามารถ decode ไฟล์: {e}")

# ===== 🤖 สนทนากับข้อมูลจากไฟล์ (RAG Chain) =====
def chat_with_vector_chain():
    if "chain" not in st.session_state:
        st.warning("⚠️ ยังไม่มีเวกเตอร์ไฟล์ใน session — กรุณาอัปโหลดไฟล์ก่อน")
        return

    # แสดงประวัติการคุย
    for msg in st.session_state.get("chat_history", []):
        st.chat_message(msg["role"]).write(msg["content"])

    # รอ prompt จากผู้ใช้
    if prompt := st.chat_input("พิมพ์คำถามของคุณเกี่ยวกับไฟล์นี้", key="chat_file_input"):
        st.chat_message("user").write(prompt)
        st.session_state["chat_history"].append({"role": "user", "content": prompt})

        try:
            response = st.session_state["chain"].run(prompt)
        except Exception as e:
            response = f"❌ เกิดข้อผิดพลาด: {e}"

        st.chat_message("assistant").write(response)
        st.session_state["chat_history"].append({"role": "assistant", "content": response})
        
# ===== 🔎 แปลงไฟล์ที่อัปโหลดเป็นข้อความเพื่อวิเคราะห์ =====
def get_split_docs(uploaded_file):
    file_name = uploaded_file.name.lower()

    if file_name.endswith(".xlsx"):
        df = pd.read_excel(uploaded_file)
        file_content = df.to_string(index=False)
    elif file_name.endswith(".csv"):
        df = pd.read_csv(uploaded_file)
        file_content = df.to_string(index=False)
    else:
        file_bytes = uploaded_file.read()
        result = from_bytes(file_bytes).best()
        if result is None:
            raise ValueError("ไม่สามารถตรวจจับ encoding ของไฟล์ได้")
        file_content = str(result)

    # ✅ ไม่แยก chunk: ส่งคืน Document เดียว
    docs = [Document(page_content=file_content)]

    return docs, file_content

# ===== 🧠 วิเคราะห์ไฟล์ด้วย Prompt ที่เลือก =====
def process_uploaded_file_for_prompt(uploaded_file):
    try:
        uploaded_file.seek(0)
        docs, file_content = get_split_docs(uploaded_file)

        # ✅ เก็บเนื้อหาเต็มใน split_docs (แม้จะมีแค่ 1 document)
        st.session_state["split_docs"] = docs
        st.session_state["file_content"] = file_content
        st.session_state["analysis_results"] = []

        st.success("✅ โหลดเนื้อหาไฟล์เรียบร้อยแล้ว")
        st.text_area("📄 แสดงเนื้อหาไฟล์", file_content, height=200, disabled=True)

    except Exception as e:
        st.error(f"❌ ไม่สามารถประมวลผลไฟล์ได้: {e}")
        st.stop()
def analyze_all_chunks_with_prompt(prompt, prompt_name):
    """รวมทุก chunk แล้ววิเคราะห์ด้วย Prompt เดียว ส่งเป็นข้อความยาวครั้งเดียว"""
    split_docs = st.session_state.get("split_docs", [])
    if not split_docs:
        st.warning("⚠️ กรุณาอัปโหลดไฟล์ก่อนวิเคราะห์")
        return

    st.info("🧠 กำลังรวมข้อมูลทั้งหมดเพื่อวิเคราะห์...")

    # 🔗 รวมเนื้อหาจากทุก chunk
    combined_text = "\n\n".join(doc.page_content for doc in split_docs)

    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": combined_text}
            ]
        )
        summary = response.choices[0].message.content
    except Exception as e:
        summary = f"❌ วิเคราะห์ไม่สำเร็จ: {e}"

    # 💾 บันทึกลง session
    st.session_state["analysis_results"] = [{
        "chunk": "ทั้งหมด",
        "summary": summary
    }]
    st.session_state["messages_prompt_file_analysis"] = [
        {"role": "system", "content": prompt},
        {"role": "assistant", "content": summary}
    ]
    st.session_state["active_prompt"] = prompt_name

    st.success("✅ วิเคราะห์เสร็จสมบูรณ์แล้ว!")
    
# ===== 💾 ปุ่มดาวน์โหลดผลลัพธ์ของ AI =====
def prepare_download_response(source_key="messages_prompt", key_suffix="default"):
    """
    สร้างปุ่มดาวน์โหลดผลลัพธ์จากข้อความล่าสุดของผู้ช่วย
    source_key: ระบุ session state ที่เก็บข้อความ เช่น "messages_prompt" หรือ "messages_prompt_file_analysis"
    key_suffix: ใช้เพื่อให้ widget key ไม่ซ้ำกันเมื่อเรียกหลายครั้ง
    """
    st.markdown("### 📥 ดาวน์โหลดผลลัพธ์")
    file_format = st.selectbox("เลือกรูปแบบไฟล์", ["txt", "md", "csv", "xlsx"],
                               key=f"file_format_selector_{key_suffix}")
    file_name_input = st.text_input("📄 ตั้งชื่อไฟล์ (ไม่ต้องใส่นามสกุล)",
                                    value="your file name", key=f"file_name_input_{key_suffix}")

    if source_key in st.session_state and st.session_state[source_key]:
        last_message = st.session_state[source_key][-1]
        if last_message["role"] == "assistant":
            ai_output = last_message["content"]
            try:
                result_file = generate_file_from_prompt(ai_output, file_format)
                full_filename = f"{file_name_input.strip()}.{file_format}"

                st.download_button(
                    label="⬇️ ดาวน์โหลดไฟล์ผลลัพธ์",
                    data=result_file,
                    file_name=full_filename,
                    mime="text/plain" if file_format == "txt" else "text/markdown"
                )
            except Exception as e:
                st.error(f"❌ ไม่สามารถสร้างไฟล์ได้: {e}")
        else:
            st.info("ℹ️ ยังไม่มีข้อความจากผู้ช่วยให้ดาวน์โหลด")
    else:
        st.info("ℹ️ กรุณาวิเคราะห์หรือเริ่มสนทนาก่อน จึงจะดาวน์โหลดได้")

# ===== 📁 แปลงข้อความ AI เป็นไฟล์ดาวน์โหลดได้หลายรูปแบบ =====
def generate_file_from_prompt(content: str, file_format: str) -> BytesIO:
    buffer = BytesIO()

    if file_format == "txt" or file_format == "md":
        buffer.write(content.encode("utf-8"))
    elif file_format == "csv":
        try:
            rows = [line.split(",") for line in content.strip().split("\n")]
            df = pd.DataFrame(rows)
            df.to_csv(buffer, index=False)
        except Exception as e:
            raise ValueError("ไม่สามารถแปลงเป็น CSV ได้: " + str(e))
    elif file_format == "xlsx":
        try:
            df = pd.DataFrame([{"เนื้อหาจาก AI": content}])
            with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
                df.to_excel(writer, index=False, sheet_name="AI Summary")
        except Exception as e:
            raise ValueError("ไม่สามารถสร้าง Excel ได้: " + str(e))

    buffer.seek(0)
<<<<<<< Updated upstream
    return buffer

=======
    return buffer
>>>>>>> Stashed changes
