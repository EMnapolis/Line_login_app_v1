import sqlite3
import sys
import os 

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config import DATABASE_NAME

# เชื่อมต่อกับ database ที่มีอยู่
conn = sqlite3.connect(DATABASE_NAME)
cursor = conn.cursor()

# เพิ่มข้อมูลผู้ใช้ 2 ราย
users_to_insert = [
    ("AdminPaint", "123456"),  # Username: AdminPaint, Password: 123456
    ("AdminTest", "123456")   # Username: userAdminTest01, Password: 123456
]

# ใช้ INSERT OR IGNORE เพื่อป้องกันการเพิ่มซ้ำกรณี username ซ้ำ
for username, password in users_to_insert:
    cursor.execute("""
        INSERT OR IGNORE INTO users (username, password)
        VALUES (?, ?)
    """, (username, password))

# บันทึกการเปลี่ยนแปลง
conn.commit()

# ปิดการเชื่อมต่อ
conn.close()

print("✅ Insert ข้อมูลสำเร็จ!")