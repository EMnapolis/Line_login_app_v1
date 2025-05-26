# config.py
import os
from dotenv import load_dotenv

load_dotenv()  # โหลดค่าจาก .env

# CHANNEL_ID = os.getenv("2007476037")
# CHANNEL_SECRET = os.getenv ("b1f80a9d4f9af5fe35d966501b4c1527")
# REDIRECT_URI = os.getenv ("https://liff.line.me/2007476037-kovOdjaB")
# STATE = os.getenv("STATE")
# ACCESS_LOG_FILE = os.getenv("ACCESS_LOG_FILE", "access_log.txt") 

CHANNEL_ID = os.getenv("CHANNEL_ID")
CHANNEL_SECRET = os.getenv("CHANNEL_SECRET")
REDIRECT_URI = os.getenv("REDIRECT_URI")
STATE = os.getenv("STATE")
ACCESS_LOG_FILE = os.getenv("ACCESS_LOG_FILE", "access_log.txt")  # default fallback