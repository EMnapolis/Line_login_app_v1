# ไฟล์: line_api.py
# =============================
# รวมฟังก์ชันที่ใช้เชื่อมต่อกับ LINE API เช่น ดึง access token, profile และส่งข้อความหา LINE User

import requests

def get_token(code, redirect_uri, client_id, client_secret):
    """ดึง access token จาก LINE ด้วย code ที่ได้หลัง login"""
    token_url = "https://api.line.me/oauth2/v2.1/token"
    payload = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "client_id": client_id,
        "client_secret": client_secret
    }
    response = requests.post(token_url, data=payload)
    return response.json()

def get_profile(access_token):
    """ดึงข้อมูลโปรไฟล์ผู้ใช้งานจาก access token"""
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.get("https://api.line.me/v2/profile", headers=headers)
    return response.json()

def send_message_to_user(user_id, message, token):
    """ส่งข้อความหา LINE User ด้วย push message API"""
    url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    payload = {
        "to": user_id,
        "messages": [{
            "type": "text",
            "text": message
        }]
    }
    response = requests.post(url, headers=headers, json=payload)
    return response.status_code

