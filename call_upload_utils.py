# call_upload_utils.py
import os
import requests
import pandas as pd
import json
import html
import sqlite3
from datetime import datetime, timedelta
from dotenv import load_dotenv
load_dotenv()  # โหลดค่าจาก .env

# สร้างโฟลเดอร์สำหรับเก็บ log และไฟล์ชั่วคราว
LOG_DIR = "logs"
TMP_DIR = "tmp"
os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(TMP_DIR, exist_ok=True)

DB_FILE = os.path.join("data", "sqdata.db")
def get_connection():
    return sqlite3.connect(DB_FILE)
#SENT_FILE = os.path.join(LOG_DIR, "sent_records.csv")  # ไฟล์เก็บ recId ที่ส่งสำเร็จแล้ว
FAILED_FILE = os.path.join(LOG_DIR, "failed_records.csv")  # ไฟล์เก็บรายการที่ล้มเหลว

def vl3cx_login():
    url = "https://villamarket.3cx.co/webclient/api/Login/GetAccessToken"
    headers = {"Content-Type": "application/json"}
    payload = {
        "Username": os.getenv("vl3cx_user"),
        "Password": os.getenv("vl3cx_pass"),
        "SecurityCode": "",
        "ReCaptchaResponse": None
    }

    response = requests.post(url, json=payload, headers=headers)
    data = response.json()

    if data.get("Status") == "AuthSuccess":
        token_info = data.get("Token", {})
        return token_info.get("access_token"), token_info.get("refresh_token")
    else:
        return None, None

def vl3cx_refresh_token(refresh_token: str):
    url = "https://villamarket.3cx.co/connect/token"
    headers = {
        "Content-type": "application/x-www-form-urlencoded;charset=UTF-8",
        "Cookie": f"RefreshTokenCookie={refresh_token}"
    }
    data = {
        "client_id": "Webclient",
        "grant_type": "refresh_token"
    }

    response = requests.post(url, headers=headers, data=data)
    result = response.json()
    return result.get("access_token")

def fetch_json(tmp_token, from_date, to_date):
    # แปลงวันที่จากไทยเป็น UTC (ลบ 7 ชั่วโมง)
    from_dt = datetime.combine(from_date, datetime.min.time())
    to_dt = datetime.combine(to_date, datetime.min.time()) + timedelta(days=1)

    # แปลงเป็นรูปแบบเวลาที่ API ต้องการ
    start_time = from_dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")
    end_time = to_dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")

    # สร้าง URL เพื่อดึง JSON จาก API 3CX
    url = (
        "https://villamarket.3cx.co/xapi/v1/Recordings?"
        f"%24top=3000&%24skip=0&%24filter=(CallType eq 'InboundExternal' or CallType eq 'OutboundExternal') "
        f"and (StartTime ge {start_time} and StartTime lt {end_time})"
        f"&%24count=true&%24orderby=StartTime asc"
    )
    headers = {"authorization": f"Bearer {tmp_token}"}
    response = requests.get(url, headers=headers)

    try:
        return response.json()
    except Exception:
        raise Exception(f"Invalid JSON returned! Status: {response.status_code}, Text: {response.text[:300]}")

# def load_sent_rec_ids():
#     if os.path.exists(SENT_FILE):
#         df = pd.read_csv(SENT_FILE)
#         if "recId" in df.columns:
#             return df["recId"].astype(str).tolist()
#         else:
#             return df.iloc[:, 0].astype(str).tolist()  # fallback ใช้คอลัมน์แรก
#     return []
def load_sent_rec_ids_db():
    with get_connection() as conn:
        cursor = conn.execute("SELECT recId FROM sent_records")
        return [row[0] for row in cursor.fetchall()]

# def save_sent_rec_id(rec_id):
#     with open(SENT_FILE, "a") as f:
#         f.write(f"{rec_id}\n")
def save_sent_rec_id_db(rec_id):
    with get_connection() as conn:
        conn.execute("""
            INSERT OR IGNORE INTO sent_records (recId) VALUES (?)
        """, (rec_id,))     

def log_failed(rec_id, error):
    with open(FAILED_FILE, "a") as f:
        f.write(f"{rec_id},{datetime.now().isoformat()},{error}\n")

def download_recording(rec_id, tmp_token):
    url = f"https://villamarket.3cx.co/xapi/v1/Recordings/Pbx.DownloadRecording(recId={rec_id})?access_token={tmp_token}"
    try:
        response = requests.get(url)
        filepath = os.path.join(TMP_DIR, f"{rec_id}.wav")
        with open(filepath, "wb") as f:
            f.write(response.content)
        return filepath
    except Exception:
        return None

def upload_file_to_asb(filepath, contact_id):
    url = f"https://ccapi-stg.villa-marketjp.com/File/UploadAsb/public?contact_id={contact_id}"
    files = {'file': (os.path.basename(filepath), open(filepath, 'rb'), 'audio/wav')}
    try:
        response = requests.post(url, files=files)
        return response.json().get("data", {}).get("fileUrl")
    except Exception:
        return None

def create_chat_room(phone, chat_token, contact_id):
    url = "https://ccapi-stg.villa-marketjp.com/ChatCenter/CreateChatRoom"
    headers = {
        "accept": "*/*",
        "Content-Type": "application/json",
        "Authorization": f"Bearer {chat_token}"
    }
    body = {
        "room_code": phone,
        "room_name": phone,
        "platform": "3cx",
        "fb_pageid": "villamarket.3cx.co",
        "contact_id": contact_id
    }
    res = requests.post(url, headers=headers, json=body)
    return res.json().get("data", {}).get("room_id")

def json_helper(fileurl):
    structure = {
        "image-url": fileurl,
        "template-type": "audio",
        "template": fileurl,
        "quick-replies": [],
        "card-list": [],
        "channels": None,
        "Attachments": None
    }
    return html.escape(json.dumps(structure))

def process_records(df, tmp_token, chat_token, contact_id):
    # ประมวลผลข้อมูลแต่ละรายการใน DataFrame และส่งข้อความเสียงเข้า ChatCenter
    output_rows = []
    for _, row in df.iterrows(): # วนลูปผ่านแต่ละแถวของ DataFrame
        try:
            rec_id = str(row["Id"])
            start_time_raw = row["StartTime"] # เวลาต้นฉบับในรูปแบบ UTC
            start_time_utc = datetime.strptime(start_time_raw, "%Y-%m-%dT%H:%M:%S.%fZ") # แปลงเป็น datetime
            start_time_local = start_time_utc + timedelta(hours=7) # แปลงเวลาเป็นเขตเวลาประเทศไทย
            start_time_str = start_time_local.strftime("%Y-%m-%d %H:%M:%S")

            # ดึงข้อมูลที่จำเป็นสำหรับข้อความ
            from_num = row["FromCallerNumber"].replace("Ext.", "")
            to_num = row["ToCallerNumber"]
            from_display = row["FromDisplayName"]
            to_display = row["ToDisplayName"]
            call_type = row["CallType"]

            # เลือกเบอร์ปลายทางตามประเภทสาย
            target_num = from_num if call_type == "InboundExternal" else to_num

            # ดาวน์โหลดไฟล์เสียง
            filepath = download_recording(rec_id, tmp_token)
            if not filepath:
                log_failed(rec_id, "Download failed")
                continue

            # อัปโหลดไฟล์ไปยัง ASB storage
            file_url = upload_file_to_asb(filepath, contact_id)
            os.remove(filepath) # ลบไฟล์ใน tmp หลังอัปโหลดสำเร็จ
            if not file_url:
                log_failed(rec_id, "Upload failed")
                continue

            # สร้างห้องสนทนา
            room_id = create_chat_room(target_num, chat_token, contact_id)

            # ปรับรูปแบบข้อความตาม CallType
            if call_type == "InboundExternal":
                from_display_clean = from_display.split(":")[-1] if ":" in from_display else from_display
                message = f"From_{from_num}_{from_display_clean}_To_{to_num}_{to_display}_เมื่อ_{start_time_str}"
            else:
                to_display_clean = "" if to_num == to_display else to_display
                message = f"From_{from_num}_{from_display}_To_{to_num}"
                if to_display_clean:
                    message += f"_{to_display_clean}"
                message += f"_เมื่อ_{start_time_str}"

            # สร้างโครงสร้างข้อความสำหรับ ChatCenter
            structure = json_helper(file_url)

            # ส่งข้อความเสียงเข้า ChatCenter
            msg_payload = {
                "room_id": room_id,
                "employee_id": 0,
                "message": message,
                "message_type": "audio",
                "message_status": "send",
                "msg_structure": structure,
                "msgid": rec_id,
                "sender": 1,
                "private_flag": "0"
            }
            requests.post("https://ccapi-stg.villa-marketjp.com/ChatCenter/CreateChatMessge",
                          headers={"Authorization": f"Bearer {chat_token}"}, json=msg_payload)

            # ส่งข้อความ text ซ้ำอีกครั้ง (เพื่อ backup หรือแจ้งเตือน)
            text_payload = msg_payload.copy()
            text_payload["message_type"] = "text"
            text_payload["msg_structure"] = ""
            text_payload["sender"] = 1 if call_type == "InboundExternal" else 1

            requests.post("https://ccapi-stg.villa-marketjp.com/ChatCenter/CreateChatMessge",
                          headers={"Authorization": f"Bearer {chat_token}"}, json=text_payload)

            row["fileUrl"] = file_url
            row["room_id"] = room_id
            output_rows.append(row)
            save_sent_rec_id_db(rec_id)

        except Exception as e:
            log_failed(rec_id, str(e))
    return pd.DataFrame(output_rows)
