# config.py
import os
from dotenv import load_dotenv
load_dotenv()  # โหลดค่าจาก .env

CHANNEL_ID = os.getenv("CHANNEL_ID")
CHANNEL_SECRET = os.getenv("CHANNEL_SECRET")
REDIRECT_URI = os.getenv("REDIRECT_URI")
STATE = os.getenv("STATE")
ACCESS_LOG_FILE = os.getenv("ACCESS_LOG_FILE", "access_log.txt")  # default fallback

OPENAI_API_KEY = os.getenv("openai_api_key")

CHAT_TOKEN = os.getenv("CHAT_TOKEN")