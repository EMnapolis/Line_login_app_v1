# utility_ai.py
from utility_chat import *
import requests

# เชื่อมต่อ SQLite
conn, cursor = init_db()
initialize_schema(conn)


# ========== ฟังก์ชันนับ Token ==========
def count_tokens(text, model="gpt-4o"):
    try:
        encoding = tiktoken.encoding_for_model(model)
    except Exception:
        encoding = tiktoken.get_encoding("cl100k_base")
    return len(encoding.encode(text))

# def attach_token_count(messages: list, model: str = "gpt-4o") -> list:
#     """
#     เพิ่ม field 'token_count' ให้กับทุกข้อความใน messages
#     ใช้ count_tokens สำหรับ GPT หรือ estimate_tokens สำหรับ LLaMA
#     """
#     for m in messages:
#         if "token_count" not in m and "content" in m:
#             if model.startswith("gpt-"):
#                 m["token_count"] = count_tokens(m["content"], model=model)
#             else:
#                 m["token_count"] = estimate_tokens(m["content"])
#     return messages

def estimate_tokens(text: str, model: str = None) -> int:
    words = len(text.split())
    return int(words / 0.75)


# ========== รวมข้อความจาก stream ของ LLaMA ==========
def parse_llama_stream_response(res):
    reply = ""
    chunks = []

    for line in res.iter_lines():
        if line:
            chunk = json.loads(line.decode("utf-8"))
            chunks.append(chunk)
            if "response" in chunk:
                reply += chunk["response"]

    full_json = chunks[-1] if chunks and chunks[-1].get("done") else {}
    return reply, full_json


# ========== ฟังก์ชันเรียกโมเดลตามชื่อ ==========
def stream_response_by_model(model_name, messages, stream_output):
    """
    รองรับ GPT (OpenAI) และ LLM Local (เช่น LLaMA ผ่าน Ollama)
    คืนค่า dict พร้อมข้อมูลบทสนทนาและ token usage
    """
    import os
    import json
    from openai import OpenAI

    reply = ""
    raw_json = {}
    prompt_tokens = 0
    completion_tokens = 0
    total_tokens = 0

    if model_name.startswith("gpt-"):
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        response = client.chat.completions.create(
            model=model_name,
            messages=messages,
            stream=True,
        )

        chunks = []  # 👈 เก็บ raw chunk
        for chunk in response:
            chunks.append(chunk.model_dump())  # ✅ เก็บ raw JSON ต่อบรรทัด
            if chunk.choices and chunk.choices[0].delta.content:
                word = chunk.choices[0].delta.content
                reply += word
                stream_output.markdown(reply + "▌", unsafe_allow_html=True)

        stream_output.markdown(reply)

        raw_json = {
            "model": model_name,
            "chunks": chunks,  # ✅ เก็บทุก chunk
            "full_reply": reply,
        }

        # นับ token (GPT เท่านั้น)
        from utility_ai import count_tokens

        prompt_tokens = sum(
            count_tokens(m["content"], model=model_name) for m in messages
        )
        completion_tokens = count_tokens(reply, model=model_name)
        total_tokens = prompt_tokens + completion_tokens

    elif model_name.startswith(("llama", "mistral", "phi")) or model_name.endswith(
        ":latest"
    ):
        from utility_ai import estimate_tokens, parse_llama_stream_response

        full_prompt = (
            "\n".join([f"{m['role']}: {m['content']}" for m in messages])
            + "\nassistant:"
        )

        res = requests.post(
            "http://localhost:11434/api/generate",
            json={"model": model_name, "prompt": full_prompt, "stream": True},
            stream=True,
        )

        reply, raw_json = parse_llama_stream_response(res)

        for i in range(0, len(reply), 10):
            stream_output.markdown(reply[: i + 10] + "▌", unsafe_allow_html=True)
        stream_output.markdown(reply)

        prompt_tokens = estimate_tokens(full_prompt)
        completion_tokens = estimate_tokens(reply)
        total_tokens = prompt_tokens + completion_tokens

    else:
        stream_output.markdown("❌ ไม่รองรับโมเดลนี้")
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
