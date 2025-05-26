import streamlit as st
import os
import json
import sqlite3
from dotenv import load_dotenv
from openai import OpenAI
from datetime import datetime
from utility import *  # ฟังก์ชัน def ทั้งหมด
from langchain.chat_models import ChatOpenAI
from langchain.document_loaders import TextLoader
from langchain.vectorstores import Chroma
from langchain.chains import ConversationalRetrievalChain
from langchain.memory import ConversationBufferMemory
from langchain.embeddings.openai import OpenAIEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
import sqlite3
from datetime import datetime
from openai import OpenAI
import os
from dotenv import load_dotenv

# ===== โหลด API Key =====
load_dotenv()
open_ai_key = os.getenv("open_ai_key")
client = OpenAI(api_key=open_ai_key)
CHAT_TOKEN = os.getenv("CHAT_TOKEN")

# ===== เชื่อมต่อ DB & สร้างตาราง (เรียกใช้จากหน้าอื่นได้เลย) =====
def init_db():
    db_path = os.path.join("data", "sqdata.db")
    conn = sqlite3.connect(db_path, check_same_thread=False)
    cursor = conn.cursor()
    return conn, cursor

# ===== โหลด schema.sql จากโฟลเดอร์ data =====
def initialize_schema(conn):
    schema_path = os.path.join("data", "schema.sql")
    if not os.path.exists(schema_path):
        raise FileNotFoundError(f"❌ ไม่พบไฟล์: {schema_path}")
    with open(schema_path, "r", encoding="utf-8") as f:
        sql_script = f.read()
    conn.executescript(sql_script)
    conn.commit()

# ===== บันทึกบทสนทนา =====
def save_conversation(conn, cursor, name, source, messages):
    cursor.execute("INSERT INTO conversations (name, source) VALUES (?, ?)", (name, source))
    conv_id = cursor.lastrowid
    for msg in messages:
        cursor.execute(
            "INSERT INTO messages (conversation_id, role, content) VALUES (?, ?, ?)",
            (conv_id, msg["role"], msg["content"])
        )
    conn.commit()

# ===== สร้างชื่อบทสนทนาด้วย AI =====
def generate_title_from_conversation(messages):
    try:
        system_prompt = {
            "role": "system",
            "content": "You are an assistant that summarizes the topic of a conversation in 5-10 Thai words."
        }
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[system_prompt] + messages + [
                {"role": "user", "content": "สรุปชื่อหัวข้อของบทสนทนานี้สั้น ๆ"}
            ]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return "บทสนทนาไม่มีชื่อ"

# ===== list ประวัติ =====
def list_conversations():
    db_path = os.path.join("data", "sqdata.db")
    conn = sqlite3.connect(db_path, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, created_at FROM conversations ORDER BY created_at DESC")
    return cursor.fetchall()

# ===== จัดการตาราง prompt =====
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
