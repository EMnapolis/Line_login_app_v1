import sqlite3
import os
import sys
from tabulate import tabulate

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config import DATABASE_NAME

conn = sqlite3.connect(DATABASE_NAME)
cursor = conn.cursor()

cursor.execute("PRAGMA table_info(history)")
all_columns = cursor.fetchall()

# เอาเฉพาะชื่อคอลัมน์ ยกเว้น 'file' และ 'response'
selected_columns = [col[1] for col in all_columns if col[1] not in ('response')]

# สร้าง query ให้เลือกเฉพาะคอลัมน์ที่ต้องการ
column_query = ", ".join(selected_columns)
cursor.execute(f"SELECT {column_query} FROM history")
rows = cursor.fetchall()

# แสดงผลลัพธ์
print(f"\n📋 Data from table 'history' ({len(rows)} rows):")
print(tabulate(rows, headers=selected_columns, tablefmt="fancy_grid", stralign="center"))


# ดึงข้อมูล history_csv
cursor.execute("PRAGMA table_info(history_csv)")
all_columns = cursor.fetchall()

# เอาเฉพาะชื่อคอลัมน์ ยกเว้น 'file' และ 'response'
selected_columns = [col[1] for col in all_columns if col[1] not in ('filedata', 'response')]

# สร้าง query ให้เลือกเฉพาะคอลัมน์ที่ต้องการ
column_query = ", ".join(selected_columns)
cursor.execute(f"SELECT {column_query} FROM history_csv")
rows = cursor.fetchall()

# แสดงผลลัพธ์
print(f"\n📋 Data from table 'history_csv' ({len(rows)} rows):")
print(tabulate(rows, headers=selected_columns, tablefmt="fancy_grid", stralign="center"))

conn.close()
