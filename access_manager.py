# ไฟล์: access_manager.py
# ========================
# จัดการการอนุมัติสิทธิ์และการเก็บบันทึกข้อมูลผู้ใช้งาน


from config import ACCESS_LOG_FILE
import os
import json
from datetime import datetime

ACCESS_LOG_FILE = "access_log.txt"  # <<== ย้ายมาที่นี่

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

def write_or_update_user(user_id, display_name, picture_url, status="PENDING"): # "APPROVED" "PENDING"
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