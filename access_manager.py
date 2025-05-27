# ไฟล์: access_manager.py
# ========================
# จัดการการอนุมัติสิทธิ์และการเก็บบันทึกข้อมูลผู้ใช้งาน


from config import ACCESS_LOG_FILE
import os
import json
import sqlite3
import pandas as pd
from datetime import datetime

#----------------------
#การจัดการ  database sqlite ใน Folder data
#----------------------
DB_FILE = os.path.join("data", "sqdata.db")
SCHEMA_FILE = os.path.join("data", "schema.sql")
def get_connection():
    return sqlite3.connect(DB_FILE)
def init_db():
    with get_connection() as conn:
        with open(SCHEMA_FILE, "r", encoding="utf-8") as f:
            conn.executescript(f.read())

def read_access_log_db():
    with sqlite3.connect(DB_FILE) as conn:
        return pd.read_sql_query("""
            SELECT 
                user_id AS "User ID",
                display_name AS "Display Name",
                picture_url AS "Picture URL",
                status AS "Status",
                updated_at AS "Last Updated"
            FROM access_login
            ORDER BY updated_at DESC;
        """, conn)

def write_or_update_user_db(user_id, display_name, picture_url, status="PENDING"):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO access_login (user_id, display_name, picture_url, status, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                display_name=excluded.display_name,
                picture_url=excluded.picture_url,
                status=excluded.status,
                updated_at=excluded.updated_at;
        """, (user_id, display_name, picture_url, status, now))

def get_approvers_db():
    with get_connection() as conn:
        cursor = conn.execute("SELECT user_id FROM access_login WHERE status = 'APPROVED'")
        return {row[0] for row in cursor.fetchall()}

def update_user_status_db(user_id, new_status):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with get_connection() as conn:
        cursor = conn.execute("""
            UPDATE access_login
            SET status = ?, updated_at = ?
            WHERE user_id = ?;
        """, (new_status, now, user_id))
        return cursor.rowcount > 0

def get_user_info_by_id(user_id):
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.execute("""
            SELECT display_name, picture_url, status
            FROM access_login
            WHERE user_id = ?
        """, (user_id,))
        row = cursor.fetchone()
        if row:
            return {"displayName": row[0], "pictureUrl": row[1], "status": row[2]}
        return None

#----------------------
#การจัดการ  ไฟล์ .txt
#----------------------
ACCESS_LOG_FILE = "access_log.txt" 

def read_access_log():
    if not os.path.exists(ACCESS_LOG_FILE):
        return {}
    users = {}
    with open(ACCESS_LOG_FILE, "r", encoding="utf-8") as f:
        for line in f:
            parts = line.strip().split(" | ")
            if len(parts) >= 5:
                _, user_id, display_name, picture_url, status = parts
                users[user_id] = {
                    "displayName": display_name,
                    "pictureUrl": picture_url,
                    "status": status
                }
    return users

def write_or_update_user(user_id, display_name, picture_url, status="PENDING"): # "APPROVED" "PENDING" "DENIED"
    users = read_access_log()
    users[user_id] = {
        "displayName": display_name,
        "pictureUrl": picture_url,
        "status": status
    }
    with open(ACCESS_LOG_FILE, "w", encoding="utf-8") as f:
        for uid, info in users.items():
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            f.write(f"{timestamp} | {uid} | {info['displayName']} | {info['pictureUrl']} | {info['status']}\n")

def get_approvers():
    """ดึง user_id ทั้งหมดที่มีสถานะ APPROVED จาก access_log.txt"""
    if not os.path.exists(ACCESS_LOG_FILE):
        return set()

    approvers = set()
    with open(ACCESS_LOG_FILE, "r", encoding="utf-8") as f:
        for line in f:
            parts = line.strip().split(" | ")
            if len(parts) == 5:
                _, user_id, _, _, status = parts
                if status == "APPROVED":
                    approvers.add(user_id)
    return approvers

def update_user_status(user_id, new_status):
    users = read_access_log()
    if user_id in users:
        users[user_id]["status"] = new_status
        with open(ACCESS_LOG_FILE, "w", encoding="utf-8") as f:
            for uid, info in users.items():
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                f.write(f"{timestamp} | {uid} | {info['displayName']} | {info['pictureUrl']} | {info['status']}\n")
        return True
    return False