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

# ✅ โหลดจาก config.py แทนการใช้ os.getenv() เอง
from config import OPENAI_API_KEY, CHAT_TOKEN

# ===== OpenAI Client =====
client = OpenAI(api_key=OPENAI_API_KEY)

# ===== เชื่อมต่อฐานข้อมูล SQLite =====
def init_db():
    db_path = os.path.join("data", "sqdata.db")
    conn = sqlite3.connect(db_path, check_same_thread=False)
    cursor = conn.cursor()
    return conn, cursor

# ===== โหลด schema.sql และรันเพื่อสร้างตาราง =====
def initialize_schema(conn):
    schema_path = os.path.join("data", "schema.sql")
    if not os.path.exists(schema_path):
        raise FileNotFoundError(f"❌ ไม่พบไฟล์: {schema_path}")
    with open(schema_path, "r", encoding="utf-8") as f:
        sql_script = f.read()
    conn.executescript(sql_script)
    conn.commit()

# ===== บันทึกบทสนทนาลงฐานข้อมูล =====
def save_conversation(conn, cursor, name, source, messages):
    cursor.execute("INSERT INTO conversations (name, source) VALUES (?, ?)", (name, source))
    conv_id = cursor.lastrowid
    for msg in messages:
        cursor.execute("INSERT INTO messages (conversation_id, role, content) VALUES (?, ?, ?)", (conv_id, msg["role"], msg["content"]))
    conn.commit()

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
        return "บทสนทนาไม่มีชื่อ"

# ===== ดึงรายชื่อบทสนทนา =====
def list_conversations():
    db_path = os.path.join("data", "sqdata.db")
    conn = sqlite3.connect(db_path, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, created_at FROM conversations ORDER BY created_at DESC")
    return cursor.fetchall()

# ===== จัดการตาราง Prompt =====
def init_prompt_table():
    db_path = os.path.join("data", "sqdata.db")
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
    db_path = os.path.join("data", "sqdata.db")
    conn = sqlite3.connect(db_path, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("REPLACE INTO prompts (name, content) VALUES (?, ?)", (name, content))
    conn.commit()

def list_prompts():
    db_path = os.path.join("data", "sqdata.db")
    conn = sqlite3.connect(db_path, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT name, content FROM prompts ORDER BY name")
    return cursor.fetchall()

def delete_prompt(name):
    db_path = os.path.join("data", "sqdata.db")
    conn = sqlite3.connect(db_path, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM prompts WHERE name = ?", (name,))
    conn.commit()

# ===== Upload file =====
def process_file_to_chain(uploaded_file):
    """แปลงไฟล์เป็นเวกเตอร์ และสร้าง Conversational RAG Chain เพื่อถามตอบจากเนื้อหาไฟล์"""
    if not uploaded_file:
        st.warning("⚠️ กรุณาอัปโหลดไฟล์ก่อน")
        return

    with st.spinner("🔄 กำลังแปลงและฝังเวกเตอร์จากไฟล์..."):
        try:
            file_bytes = uploaded_file.read()

            # 🧠 พยายามตรวจจับ encoding ด้วย charset_normalizer
            try:
                from charset_normalizer import from_bytes
                result = from_bytes(file_bytes).best()
                if result:
                    file_content = str(result)
                else:
                    raise ValueError("charset_normalizer ไม่สามารถตรวจจับได้")
            except Exception:
                try:
                    file_content = file_bytes.decode("utf-8")
                except UnicodeDecodeError:
                    file_content = file_bytes.decode("iso-8859-1")  # fallback เผื่อเป็น encoding ไทยแบบเก่า

            # 📝 แสดง preview ข้อมูลต้นฉบับ
            st.text_area("📖 ตัวอย่างเนื้อหาในไฟล์", file_content[:1000], height=200, disabled=True)

            # 📄 แปลงไฟล์เป็น chunks
            docs = [Document(page_content=file_content)]
            text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
            split_docs = text_splitter.split_documents(docs)

            # 🧬 ฝังเวกเตอร์
            embeddings = OpenAIEmbeddings(openai_api_key=OPENAI_API_KEY)
            vectorstore = Chroma.from_documents(split_docs, embeddings)

            # 🔁 สร้าง RAG Chain
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

# ===== ให้ผู้ใช้โต้ตอบกับ chain ที่สร้างจากเวกเตอร์ของไฟล์ =====
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
        
# ===== โหลดไฟล์และแยกเป็น chunk สำหรับการวิเคราะห์ =====
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

# ===== ใช้สำหรับ Tab Prompt: ประมวลผลไฟล์ที่อัปโหลดและแสดงผลใน session =====
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
        
# ===== ใช้สำหรับ Tab Prompt: ประมวลผลไฟล์ที่อัปโหลดและแสดงผลใน session =====
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
    
# ===== ใช้สำหรับ Tab Prompt: สร้างไฟล์ดาวน์โหลดจากผลลัพธ์ล่าสุด =====
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

# ===== สร้างไฟล์ผลลัพธ์ให้ดาวน์โหลดได้ในหลายรูปแบบ =====
def generate_file_from_prompt(content: str, file_format: str) -> BytesIO:
    buffer = BytesIO()

    if file_format == "txt" or file_format == "md":
        buffer.write(content.encode("utf-8"))
    elif file_format == "csv":
        rows = [line.split(",") for line in content.strip().split("\n")]
        df = pd.DataFrame(rows)
        df.to_csv(buffer, index=False)
    elif file_format == "xlsx":
        df = pd.DataFrame([{"เนื้อหาจาก AI": content}])
        with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
            df.to_excel(writer, index=False, sheet_name="AI Summary")
    else:
        raise ValueError("Unsupported file format")

    buffer.seek(0)
    return buffer