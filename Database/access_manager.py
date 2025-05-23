import sqlite3
import sys 
import os

from tabulate import tabulate 

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config import DATABASE_RECORDING_UPLOAD_NAME, DATABASE_FOLDER

DATABASE_PATH = os.path.join(DATABASE_FOLDER, DATABASE_RECORDING_UPLOAD_NAME)

# เชื่อมต่อหรือสร้าง database

def create_recording_upload_db():
    conn = sqlite3.connect(DATABASE_RECORDING_UPLOAD_NAME)
    cursor = conn.cursor()
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS access_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        user_id TEXT NOT NULL UNIQUE,
        display_name TEXT NOT NULL,
        picture_url TEXT NOT NULL, 
        STATUS TEXT NOT NULL          
    );
    """)

    # บันทึกการเปลี่ยนแปลง
    conn.commit()

    # ปิดการเชื่อมต่อ
    conn.close()

    print("✅ Create ข้อมูลสำเร็จ!")

def write_or_update_user_db(user_id, display_name, picture_url, status="PENDING", timestamp=None):
    check_db()
    if timestamp is None:
        from datetime import datetime, timedelta
        timestamp = (datetime.utcnow() + timedelta(hours=7)).strftime('%d/%m/%Y %H:%M:%S')

    conn = sqlite3.connect(DATABASE_RECORDING_UPLOAD_NAME)
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO access_log (user_id, display_name, picture_url, status, timestamp)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            display_name = excluded.display_name,
            picture_url  = excluded.picture_url,
            status       = excluded.status,
            timestamp    = excluded.timestamp
    """, (user_id, display_name, picture_url, status, timestamp))

    conn.commit()
    conn.close()
    print("✅ Write or Update ข้อมูลสำเร็จ!")


def show_user_db():

    conn = sqlite3.connect(DATABASE_RECORDING_UPLOAD_NAME)
    cursor = conn.cursor()

    # ดึงชื่อคอลัมน์ทั้งหมด
    cursor.execute("PRAGMA table_info(access_log)")
    all_columns = cursor.fetchall()
    column_names = [col[1] for col in all_columns]

    # ดึงข้อมูลทั้งหมดในตาราง
    cursor.execute("SELECT * FROM access_log")
    rows = cursor.fetchall()

    # แสดงผล
    print(f"\n📋 ข้อมูลทั้งหมดในตาราง 'access_log' ({len(rows)} rows):")
    print(tabulate(rows, headers=column_names, tablefmt="fancy_grid", stralign="center"))

    conn.close()


def update_user_status_db(user_id, new_status):
    # ตรวจสอบหรือเชื่อมต่อกับ DB
    conn = sqlite3.connect(DATABASE_RECORDING_UPLOAD_NAME)
    cursor = conn.cursor()

    # อัปเดตสถานะของผู้ใช้
    cursor.execute("""
        UPDATE access_log
        SET status = ?
        WHERE user_id = ?
    """, (new_status, user_id))

    # บันทึกและปิดการเชื่อมต่อ
    conn.commit()
    conn.close()

    print(f"✅ อัปเดตสถานะของ {user_id} เป็น {new_status} สำเร็จ!")

def check_db():
    conn = sqlite3.connect(DATABASE_RECORDING_UPLOAD_NAME)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT name FROM sqlite_master WHERE type='table' AND name='access_log';
    """)
    
    result = cursor.fetchone()

    if (result is None):
        create_recording_upload_db()

def get_approvers_db():
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    approvers = set()

    # ดึง user_id ทั้งหมดที่มีสถานะ APPROVED
    cursor.execute("SELECT user_id FROM access_log WHERE status = 'APPROVED'")
    rows = cursor.fetchall()

    for (user_id,) in rows:
        approvers.add(user_id)

    conn.close()
    return approvers

def read_access_log_db():
    users = {}

    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()


    # อ่านข้อมูลทั้งหมดจากตาราง
    cursor.execute("SELECT user_id, display_name, picture_url, status FROM access_log")
    rows = cursor.fetchall()

    for row in rows:
        user_id, display_name, picture_url, status = row
        users[user_id] = {
            "displayName": display_name,
            "pictureUrl": picture_url,
            "status": status
        }

    conn.close()
    return users


def insert_sample_data():
    data_list = [
        {
            "user_id": "Udebug123456",
            "display_name": "ทดสอบระบบ TEST",
            "profile_image_url": "https://i.imgur.com/1Q9Z1Zm.png",
            "status": "APPROVED"
        },
        {
            "user_id": "Ua30c7125dae963c2a4a79141e16e3150",
            "display_name": "Master M Unicorntech",
            "profile_image_url": "https://profile.line-scdn.net/0hTR6SFU8EC30bKhkPtpp1Amt6CBc4W1JvMhhNHCZ5BUwgGkp4ZEhEGSx4XEwkGk0iZU4RSCsvUEoXOXwbBXz3SRwaVUoiHUwvNkxFnA",
            "status": "APPROVED"
        }
    ]

    for item in data_list:
        write_or_update_user_db(
            item["user_id"],
            item["display_name"],
            item["profile_image_url"],
            item["status"]
        )

if __name__ == "__main__":
    # create_recording_upload_db()
    # insert_sample_data()
    show_user_db()