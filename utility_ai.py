# utility_ai.py
from utility_chat import *
import requests
import subprocess

# เชื่อมต่อ SQLite
conn, cursor = init_db()
initialize_schema(conn)
# ==== AI KEY ====

# API / Auth
CHANNEL_ID = os.getenv("CHANNEL_ID")
CHANNEL_SECRET = os.getenv("CHANNEL_SECRET")
REDIRECT_URI = os.getenv("REDIRECT_URI")
STATE = os.getenv("STATE")
CHAT_TOKEN = os.getenv("CHAT_TOKEN")

# Logging
ACCESS_LOG_FILE = os.getenv("ACCESS_LOG_FILE", "access_log.txt")

# AI Keys
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")  # ✅ ใช้ชื่อให้ตรงกัน
OLLAMA_SERVER_URL = os.getenv("OLLAMA_SERVER_URL")

# ========== ฟังก์ชันนับ Token ==========
def count_tokens(text, model="gpt-4o"):
    try:
        encoding = tiktoken.encoding_for_model(model)
    except Exception:
        encoding = tiktoken.get_encoding("cl100k_base")
    return len(encoding.encode(text))

def estimate_tokens(text: str, model: str = None) -> int:
    words = len(text.split())
    return int(words / 0.75)


# ========== รวมข้อความจาก stream ของ LLaMA ==========
def parse_llama_stream_response(res):
    import json

    reply = ""
    raw_chunks = []
    decoder = json.JSONDecoder()

    for line in res.iter_lines():
        if line:
            try:
                line_str = line.decode("utf-8").strip()

                # กรณีมีหลาย JSON object ต่อบรรทัด
                while line_str:
                    obj, idx = decoder.raw_decode(line_str)
                    raw_chunks.append(obj)
                    reply += obj.get("response", "")
                    line_str = line_str[idx:].lstrip()

            except Exception as e:
                print("❌ Error decoding JSON chunk:", e)
                continue

    return reply, {"chunks": raw_chunks, "full_reply": reply}


# ========== ฟังก์ชันเรียกโมเดลตามชื่อ ==========
def stream_response_by_model(model_name, messages, stream_output):
    """
    รองรับ GPT (OpenAI), Ollama (LLaMA/Mistral/etc.), และ fallback
    คืนค่า dict พร้อมข้อมูลบทสนทนาและ token usage
    """
    import json, os, requests
    from openai import OpenAI

    reply = ""
    raw_json = {}
    prompt_tokens = 0
    completion_tokens = 0
    total_tokens = 0

    # ========== GPT MODELS ==========
    if model_name.startswith("gpt-"):
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        response = client.chat.completions.create(
            model=model_name,
            messages=messages,
            stream=True,
        )

        chunks = []
        for chunk in response:
            if st.session_state.get("stop_chat", False):
                stream_output.markdown("🛑 หยุดแสดงผลแล้ว")
                break
            chunks.append(chunk.model_dump())
            if chunk.choices and chunk.choices[0].delta.content:
                word = chunk.choices[0].delta.content
                reply += word
                stream_output.markdown(reply + "▌", unsafe_allow_html=True)

        stream_output.markdown(reply)
        st.session_state["stop_chat"] = False

        raw_json = {
            "model": "gpt-4o",
            "chunks": chunks,
            "full_reply": reply,
        }

        prompt_tokens = sum(
            count_tokens(m["content"], model=model_name) for m in messages
        )
        completion_tokens = count_tokens(reply, model=model_name)
        total_tokens = prompt_tokens + completion_tokens

    # ========== OLLAMA MODELS ==========
    elif True:  # Fallback สำหรับโมเดลใดๆ ที่ไม่ใช่ GPT
        llama_server = os.getenv(
            "OLLAMA_SERVER_API", "http://localhost:11434/api/generate"
        )
        full_prompt = (
            "\n".join([f"{m['role']}: {m['content']}" for m in messages])
            + "\nassistant:"
        )

        try:
            res = requests.post(
                llama_server,
                json={"model": model_name, "prompt": full_prompt, "stream": True},
                stream=True,
            )

            reply = ""
            raw_chunks = []
            decoder = json.JSONDecoder()

            for line in res.iter_lines():
                if st.session_state.get("stop_chat", False):
                    stream_output.markdown("🛑 หยุดแสดงผลแล้ว")
                    break
                if line:
                    try:
                        line_str = line.decode("utf-8").strip()
                        while line_str:
                            obj, idx = decoder.raw_decode(line_str)
                            raw_chunks.append(obj)
                            reply += obj.get("response", "")
                            line_str = line_str[idx:].lstrip()
                            stream_output.markdown(reply + "▌", unsafe_allow_html=True)
                    except Exception as e:
                        print("❌ Error decoding JSON chunk:", e)

            stream_output.markdown(reply)
            st.session_state["stop_chat"] = False

            raw_json = {
                "model": model_name,
                "chunks": raw_chunks,
                "full_reply": reply,
            }

            prompt_tokens = estimate_tokens(full_prompt)
            completion_tokens = estimate_tokens(reply)
            total_tokens = prompt_tokens + completion_tokens

        except Exception as e:
            stream_output.markdown(f"❌ ไม่สามารถเชื่อมต่อกับ Ollama ได้: {e}")
            return {
                "reply": "",
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
                "response_json": "{}",
            }

    return {
        "reply": reply,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "response_json": json.dumps(raw_json, ensure_ascii=False),
    }


def get_ollama_models():
    try:
        response = requests.get(f"{OLLAMA_SERVER_URL}/api/tags")
        response.raise_for_status()
        data = response.json()
        return [m["name"] for m in data.get("models", [])]
    except Exception as e:
        print(f"❌ ไม่สามารถดึงรายชื่อโมเดลจาก Ollama ได้: {e}")
        return []


def display_ai_response_info(model_choice, base_messages, stream_output):
    """
    เรียก model แล้วแสดงผล พร้อมข้อมูล tokens, model และเวลาใช้
    ส่งคืน result["reply"] ด้วย
    """
    start_time = time.time()

    result = stream_response_by_model(model_choice, base_messages, stream_output)

    end_time = time.time()
    duration = round(end_time - start_time, 2)

    reply = result["reply"]
    stream_output.markdown(reply)

    st.caption(
        f"📌 ใช้โมเดล: `{model_choice}` | "
        f"Tokens: Prompt = {result['prompt_tokens']}, Completion = {result['completion_tokens']}, "
        f"รวม = {result['total_tokens']} | "
        f"⏱️ ใช้เวลา {duration} วินาที"
    )

    return result


# 🧠 ฟังก์ชันตรวจสอบ token quota
def check_token_quota():
    from utility_chat import init_db

    conn, cursor = init_db()
    current_user = st.session_state.get("user_id", "")
    role = st.session_state.get("role", "").lower()

    # ✅ ดึงรวม Token ที่ใช้
    cursor.execute(
        """
        SELECT SUM(total_tokens) FROM token_usage
        WHERE user_id = ?
        """,
        (current_user,),
    )
    used_token = cursor.fetchone()[0] or 0

    # ✅ ดึง quota override ล่าสุดจาก DB
    cursor.execute(
        """
        SELECT quota_override FROM token_usage
        WHERE user_id = ? AND quota_override IS NOT NULL
        ORDER BY id DESC LIMIT 1
        """,
        (current_user,),
    )
    quota_row = cursor.fetchone()
    quota_limit = quota_row[0] if quota_row else 1_000_000  # DEFAULT_QUOTA fallback

    # ✅ คำนวณ % ที่ใช้แล้ว
    percent_used = round((used_token / quota_limit) * 100, 2)

    # ⚠️ แจ้งเตือนเมื่อเกิน 90%
    if percent_used >= 90 and used_token < quota_limit:
        st.warning(
            f"""
            ⚠️ คุณใช้ Token ไปแล้ว {percent_used}%  
            🔢 ใช้ไป: `{used_token:,}` จากโควต้า `{quota_limit:,}` Tokens  
            🧭 กรุณาวางแผนการใช้งานให้เหมาะสม
            """
        )

    # ❌ หยุดใช้งานหากเกินโควต้า
    if used_token >= quota_limit and role not in ["admin", "super admin"]:
        st.error(
            f"""
            ❌ คุณใช้ Token เกินโควต้าที่กำหนดแล้ว  
            🔢 ใช้ไป: `{used_token:,}` จากโควต้า `{quota_limit:,}` Tokens  
            🛑 กรุณาติดต่อผู้ดูแลระบบเพื่อขอเพิ่มโควต้า หรือรอรอบใหม่
            """
        )
        st.stop()
