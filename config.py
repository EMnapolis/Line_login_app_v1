from dotenv import load_dotenv
import os

load_dotenv()  # โหลดตัวแปรจาก .env

# ไฟล์: config.py
# =============================
# ใช้เก็บค่าคงที่และการตั้งค่าหลักของระบบ เช่น LINE Channel ID, Secret, Redirect URI

CHANNEL_ID = os.getenv("CHANNEL_ID", "default_channel_id")
CHANNEL_SECRET = os.getenv("CHANNEL_SECRET", "default_secret")
REDIRECT_URI = os.getenv("REDIRECT_URI", "http://localhost")
STATE = os.getenv("STATE", "my-login-session") # ค่า state สำหรับความปลอดภัยของ OAuth2

ACCESS_LOG_FILE = os.getenv("ACCESS_LOG_FILE", "access_log.txt")

# โฟลเดอร์สั่ง Prompts 
PROMPT_FOLDER = os.getenv("PROMPT_FOLDER", "Prompts")

# โฟลเดอร์สั่ง Database
DATABASE_FOLDER = os.getenv("DATABASE_FOLDER", "Database")

# ชื่อ Database ที่ใช้เก็บ Data และ History ของ Users 
DATABASE_NAME = os.getenv("DATABASE_NAME", "llm_prompt.db")

DATABASE_RECORDING_UPLOAD_NAME = os.getenv("DATABASE_RECORDING_UPLOAD_NAME", "recording_upload.db")

CHAT_TOKEN = os.getenv("CHAT_TOKEN", "XXXXX")