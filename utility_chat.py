# utility.py
import streamlit as st
import os
import sqlite3
import pandas as pd
from io import StringIO
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
import json
import time
import math
import requests
# ==== import libary ====

# ==== global path ====
db_folder = os.path.join("data")
db_path = os.path.join("data", "sqdata.db")
schema_path = os.path.join("data", "schema.sql")
user_id = st.session_state.get("user_id")
# ==== global path ====

# ✅ โหลดจาก config.py แทนการใช้ os.getenv() เอง
from config import OPENAI_API_KEY,CHAT_TOKEN

# ===== OpenAI Client =====
client = OpenAI(api_key=OPENAI_API_KEY)

# ===== เชื่อมต่อฐานข้อมูล SQLite =====
def init_db():
    if not os.path.exists(db_folder):
        os.makedirs(db_folder)

    first_time = not os.path.exists(db_path)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    
    if first_time:
        initialize_schema(conn)
        
    return conn, conn.cursor()

# ===== โหลด schema.sql และรันเพื่อสร้างตาราง =====
def initialize_schema(conn, schema_path=schema_path):
    """
    โหลดและรัน SQL schema จากไฟล์ .sql ที่ระบุ
    """
    if not os.path.exists(schema_path):
        raise FileNotFoundError(f"❌ ไม่พบไฟล์ schema: {schema_path}")

    with open(schema_path, "r", encoding="utf-8") as f:
        sql_script = f.read().strip()

    if not sql_script:
        raise ValueError("⚠️ ไฟล์ schema ว่างเปล่า")

    try:
        conn.executescript(sql_script)
        conn.commit()
        print("✅ สร้าง schema เรียบร้อยแล้ว")
    except Exception as e:
        conn.rollback()
        raise RuntimeError(f"❌ เกิดข้อผิดพลาดระหว่างสร้าง schema: {e}")


# ===== บันทึกบทสนทนาลงฐานข้อมูล =====
def save_conversation_if_ready(
    conn, cursor, messages_key, source="chat_gpt", **token_usage
):
    messages = st.session_state.get(messages_key, [])
    conv_key = f"conversation_id_{messages_key}"
    last_key = f"last_saved_count_{messages_key}"
    conv_id = st.session_state.get(conv_key)
    last_saved_count = st.session_state.get(last_key, 0)
    user_id = st.session_state.get("user_id", "guest")

    if len(messages) >= 2 and len(messages) > last_saved_count:
        last_two = messages[-2:]
        if last_two[0]["role"] == "user" and last_two[1]["role"] == "assistant":
            if conv_id is None:
                title = generate_title_from_conversation(messages)
                cursor.execute(
                    """
                    INSERT INTO conversations (
                        user_id, title, source,
                        prompt_tokens, completion_tokens, total_tokens
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        user_id,
                        title,
                        source,
                        token_usage.get("prompt_tokens", 0),
                        token_usage.get("completion_tokens", 0),
                        token_usage.get("total_tokens", 0),
                    ),
                )
                conv_id = cursor.lastrowid
                st.session_state[conv_key] = conv_id

            for msg in messages[last_saved_count:]:
                cursor.execute(
                    """
                    INSERT INTO messages (
                        user_id, conversation_id, role, content,
                        prompt_tokens, completion_tokens, total_tokens
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        user_id,
                        conv_id,
                        msg.get("role", "user"),
                        msg.get("content", ""),
                        msg.get("prompt_tokens", 0),
                        msg.get("completion_tokens", 0),
                        msg.get("total_tokens", 0),
                    ),
                )
                message_id = cursor.lastrowid

                if "response_json" in msg:
                    cursor.execute(
                        """
                        INSERT INTO raw_json (conversation_id, message_id, response_json)
                        VALUES (?, ?, ?)
                        """,
                        (conv_id, message_id, msg["response_json"]),
                    )

            conn.commit()
            st.session_state[last_key] = len(messages)
            st.toast(f"💾 บันทึกบทสนทนาใหม่จาก {source}")


# ===== ใช้ AI ตั้งชื่อบทสนทนาแบบย่อ =====
def generate_title_from_conversation(messages):
    try:
        system_prompt = {"role": "system", "content": "You are an assistant that summarizes the topic of a conversation in 5-10 Thai words."}
        response = client.chat.completions.create(
            model="model_name",
            messages=[system_prompt] + messages + [{"role": "user", "content": "สรุปชื่อหัวข้อของบทสนทนานี้สั้น ๆ"}]
        )
        return response.choices[0].message.content.strip()
    except Exception:
        return "บทสนทนาใหม่" if not messages else messages[0].get("content", "บทสนทนาใหม่")[:30]

# ===== ดึงรายชื่อบทสนทนา =====
def list_conversations(user_id=None):
    db_path = os.path.join("data", "sqdata.db")
    conn = sqlite3.connect(db_path, check_same_thread=False)

    # เพิ่ม token columns
    query = """
        SELECT id, user_id, title, source,
               prompt_tokens, completion_tokens, total_tokens,
               created_at
        FROM conversations
    """
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
            prompt_name TEXT,
            user_id TEXT NOT NULL,
            content TEXT,
            prompt_tokens INTEGER,
            completion_tokens INTEGER,
            total_tokens INTEGER,
            PRIMARY KEY (prompt_name, user_id)
        )
    """)
    conn.commit()
def save_prompt(prompt_name, content):
    user_id = st.session_state.get("user_id")
    if not user_id:
        st.warning("⛔ กรุณาเข้าสู่ระบบ")
        return
    conn = sqlite3.connect(db_path, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("""
        REPLACE INTO prompts (prompt_name, user_id, content, prompt_tokens, completion_tokens, total_tokens)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (prompt_name, user_id, content, 0, 0, 0))  # ปรับ token = 0 หรือให้รับ parameter ถ้ามี
    conn.commit()
    conn.close()
def list_prompts():
    user_id = st.session_state.get("user_id")
    role = st.session_state.get("Role", "user")

    conn = sqlite3.connect(db_path, check_same_thread=False)
    cursor = conn.cursor()

    if role == "admin":
        cursor.execute("SELECT prompt_name, content FROM prompts ORDER BY prompt_name")
    else:
        cursor.execute("SELECT prompt_name, content FROM prompts WHERE user_id = ? ORDER BY prompt_name", (user_id,))
    results = cursor.fetchall()
    conn.close()
    return results
def delete_prompt(name):
    user_id = st.session_state.get("user_id")
    role = st.session_state.get("Role", "user")

    conn = sqlite3.connect(db_path, check_same_thread=False)
    cursor = conn.cursor()

    if role == "admin":
        cursor.execute("DELETE FROM prompts WHERE prompt_name = ?", (name,))
    else:
        cursor.execute("DELETE FROM prompts WHERE prompt_name = ? AND user_id = ?", (name, user_id))

    conn.commit()
    conn.close()

## ============================== เกี่ยวกับไฟล์ ==============================
# ===== ตรวจจับ encoding และแปลงเป็นข้อความ =====
# ===== ตรวจจับ encoding และแปลงเป็นข้อความ =====
def try_decode_file(file_bytes: bytes) -> str:
    try:
        result = from_bytes(file_bytes).best()
        if result:
            return str(result)
    except Exception:
        pass
    try:
        return file_bytes.decode("utf-8")
    except UnicodeDecodeError:
        return file_bytes.decode("iso-8859-1", errors="replace")
# ===== ประมวลผลไฟล์และสร้าง RAG Chain =====
def process_file_to_chain(uploaded_file):
    if not uploaded_file:
        st.warning("⚠️ กรุณาอัปโหลดไฟล์ก่อน")
        return

    with st.spinner("🔄 กำลังประมวลผลไฟล์..."):
        try:
            file_bytes = uploaded_file.read()
            file_content = try_decode_file(file_bytes)
            st.text_area("📖 ตัวอย่างเนื้อหา", file_content[:1000], height=200, disabled=True)

            doc = Document(page_content=file_content)
            splitter = RecursiveCharacterTextSplitter(chunk_size=3000, chunk_overlap=300)
            chunks = splitter.split_documents([doc])
            st.success(f"📚 แบ่งเนื้อหาออกเป็น {len(chunks)} ส่วนย่อย")

            embeddings = OpenAIEmbeddings(openai_api_key=OPENAI_API_KEY)
            vectorstore = Chroma.from_documents(chunks, embedding=embeddings)

            chain = ConversationalRetrievalChain.from_llm(
                llm=ChatOpenAI(model="model_name", temperature=0, openai_api_key=OPENAI_API_KEY),
                retriever=vectorstore.as_retriever(),
                memory=ConversationBufferMemory(memory_key="chat_history", return_messages=True),
            )

            st.session_state["chain"] = chain
            st.session_state["chat_history"] = []
            st.session_state["file_content"] = file_content
            st.success("✅ โหลดและแบ่งเนื้อหาเรียบร้อยแล้ว พร้อมใช้งาน")

        except Exception as e:
            st.error(f"❌ เกิดข้อผิดพลาด: {e}")
# ===== 🔎 อ่านเนื้อหาจากไฟล์ที่อัปโหลด =====
def read_uploaded_file(file_name, uploaded_file, chunk_size=5000):
    file_name = file_name.lower()
    my_bar = st.progress(0, text="📥 กำลังโหลดเนื้อหาไฟล์...")
    uploaded_file.seek(0)

    if file_name.endswith(".xlsx"):
        df = pd.read_excel(uploaded_file)
        content = df.to_string(index=False)
    elif file_name.endswith(".csv"):
        df = pd.read_csv(uploaded_file)
        content = df.to_string(index=False)
    else:
        file_bytes = uploaded_file.read()
        result = from_bytes(file_bytes).best()
        content = str(result) if result else file_bytes.decode("utf-8")

    total_parts = math.ceil(len(content) / chunk_size)
    collected = []

    for i in range(total_parts):
        part = content[i * chunk_size : (i + 1) * chunk_size]
        collected.append(part)
        percent = int((i + 1) / total_parts * 100)
        my_bar.progress(percent, text=f"📄 ประมวลผลส่วนที่ {i+1}/{total_parts} ({percent}%)")
        time.sleep(0.01)

    my_bar.empty()
    return "".join(collected)
# ===== 💬 เพิ่มข้อความลงในประวัติแชท =====
def append_chat(role, content, state_key="chat_history"):
    """เพิ่มข้อความลงใน session chat"""
    st.chat_message(role).write(content)
    st.session_state.setdefault(state_key, []).append({
        "role": role,
        "content": content
    })
# ===== แปลงไฟล์เป็น Document สำหรับ LLM =====
def get_split_docs(uploaded_file, chunk_size=3000, chunk_overlap=200):
    """แปลงไฟล์เป็นหลาย Document และแสดงความคืบหน้า"""
    file_name = uploaded_file.name.lower()

    # อ่านเนื้อหาไฟล์
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

    # สร้าง Document เดียวก่อน
    doc = Document(page_content=file_content)

    # แบ่งเป็นหลาย chunk
    splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    all_chunks = splitter.split_documents([doc])
    total = len(all_chunks)

    # แสดง progress
    st.info(f"📄 แบ่งไฟล์ออกเป็น {total} ส่วน กำลังประมวลผล...")

    progress_bar = st.progress(0)
    processed_chunks = []
    for i, chunk in enumerate(all_chunks):
        processed_chunks.append(chunk)

        # แสดงความคืบหน้า
        percent_complete = int((i + 1) / total * 100)
        progress_bar.progress(percent_complete)
        time.sleep(0.01)  # จำลอง delay (ลบออกจริง)

    st.success("✅ แบ่งเนื้อหาเรียบร้อย พร้อมใช้งาน!")

    return processed_chunks, file_content
# ===== เรียก GPT และพยายามแปลงผลลัพธ์เป็นตาราง (DataFrame) =====
def call_openai_with_parsing(full_input, system_prompt):
    from openai import OpenAI
    client = OpenAI(api_key=OPENAI_API_KEY)

    base_messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": full_input}
    ]

    response = client.chat.completions.create(
        model="model_name",
        messages=base_messages
    )

    reply = response.choices[0].message.content
    usage = response.usage
    raw_json = json.dumps(response.model_dump(), ensure_ascii=False)

    df_result = None
    try:
        if "|" in reply and "---" in reply:
            lines = [line for line in reply.splitlines() if "|" in line and not line.strip().startswith("---")]
            cleaned = "\n".join(lines)
            df_result = pd.read_csv(StringIO(cleaned), sep="|").dropna(axis=1, how="all")
        elif "," in reply:
            df_result = pd.read_csv(StringIO(reply))
    except Exception:
        df_result = None

    return reply, df_result, usage, raw_json
# ===== 🧠 วิเคราะห์ไฟล์ด้วย Prompt ที่เลือก =====
def process_uploaded_file_for_prompt(uploaded_file):
    try:
        uploaded_file.seek(0)
        file_name = uploaded_file.name.lower()

        if file_name.endswith(".txt"):
            file_content = uploaded_file.read().decode("utf-8", errors="ignore")
        elif file_name.endswith(".csv"):
            df = pd.read_csv(uploaded_file)
            file_content = df.to_csv(index=False)
        elif file_name.endswith(".xlsx"):
            df = pd.read_excel(uploaded_file)
            file_content = df.to_csv(index=False)
        else:
            raise ValueError("ไม่รองรับประเภทไฟล์นี้")

        st.session_state["file_content"] = file_content
        st.session_state["analysis_results"] = []

        st.success("✅ โหลดเนื้อหาไฟล์เรียบร้อยแล้ว")
        st.text_area("📄 แสดงเนื้อหาไฟล์", file_content[:3000], height=200, disabled=True)


    except Exception as e:
        st.error(f"❌ ไม่สามารถประมวลผลไฟล์ได้: {e}")
        st.stop()
# 📥 ปุ่มดาวน์โหลดผลลัพธ์ AI (txt / md)
def show_download_section():
    if st.session_state.get("show_download"):
        st.markdown("### 📥 ดาวน์โหลดผลลัพธ์")

        file_format = st.selectbox(
            "📄 เลือกรูปแบบไฟล์", ["txt", "csv", "xlsx"], key="download_format"
        )

        file_name = st.text_input(
            "📁 ตั้งชื่อไฟล์", value="analysis_result", key="download_filename"
        )

        full_filename = f"{file_name.strip()}.{file_format}"
        file_bytes = BytesIO()

        # ▶️ กรณีเป็นตาราง (csv, xlsx)
        if (
            file_format in ["csv", "xlsx"]
            and st.session_state.get("analysis_result_table") is not None
        ):
            raw_data = st.session_state["analysis_result_table"]

            # 🧠 ตรวจสอบรูปแบบข้อมูลและสร้าง DataFrame
            if isinstance(raw_data, list):
                if all(isinstance(item, list) for item in raw_data):
                    # ⛳️ list of list → แยก header กับข้อมูล
                    if len(raw_data) >= 2:
                        header = raw_data[0]
                        rows = raw_data[1:]
                        df = pd.DataFrame(rows, columns=header)
                    else:
                        st.warning("⚠️ ไม่มีข้อมูลให้แสดง")
                        return
                elif all(isinstance(item, dict) for item in raw_data):
                    df = pd.DataFrame(raw_data)
                else:
                    st.warning(
                        "⚠️ ไม่รองรับรูปแบบข้อมูลนี้ (ต้องเป็น list of list หรือ list of dict)"
                    )
                    return
            else:
                st.warning("⚠️ ไม่สามารถแปลงข้อมูลเป็นตารางได้")
                return

            with st.expander("🔍 แสดงผลลัพธ์แบบตาราง"):
                st.dataframe(df)

            if file_format == "csv":
                df.to_csv(file_bytes, index=False, encoding="utf-8-sig")
                mime_type = "text/csv"
            elif file_format == "xlsx":
                with pd.ExcelWriter(file_bytes, engine="xlsxwriter") as writer:
                    df.to_excel(writer, index=False, sheet_name="Result")
                mime_type = (
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

        else:
            # ▶️ กรณีเป็นข้อความธรรมดา (txt)
            content = st.session_state.get("analysis_result", "")
            if not content.strip():
                st.warning("⚠️ ไม่มีข้อมูลสำหรับบันทึกเป็นไฟล์ข้อความ")
                return

            with st.expander("🔍 แสดงเนื้อหาที่จะบันทึก"):
                st.text(content)
            file_bytes.write(content.encode("utf-8"))
            mime_type = "text/plain"

        file_bytes.seek(0)

        # ⬇️ ปุ่มดาวน์โหลด
        st.download_button(
            label="⬇️ ดาวน์โหลดผลลัพธ์",
            data=file_bytes,
            file_name=full_filename,
            mime=mime_type,
        )

## ============================== เกี่ยวกับไฟล์ ==============================