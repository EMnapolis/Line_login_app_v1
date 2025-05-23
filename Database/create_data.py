import sqlite3
import sys 
import os 

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config import DATABASE_NAME

# เชื่อมต่อหรือสร้าง database
conn = sqlite3.connect(DATABASE_NAME)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password TEXT NOT NULL
);
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL,
    header TEXT NOT NULL,
    prompt TEXT NOT NULL,
    response TEXT NOT NULL,
    source TEXT DEFAULT 'text',
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(username, header, prompt, response, source, timestamp),
    UNIQUE(username, timestamp)
);
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS history_csv (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL,
    header TEXT NOT NULL,
    prompt TEXT NOT NULL,
    response TEXT NOT NULL,
    filedata BLOB,
    source TEXT DEFAULT 'csv',
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(username, header, prompt, response, source, timestamp),
    UNIQUE(username, timestamp)
);
""")


# บันทึกการเปลี่ยนแปลง
conn.commit()

# ปิดการเชื่อมต่อ
conn.close()

print("✅ Create ข้อมูลสำเร็จ!")
