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

# ========== ฟังก์ชันเรียกโมเดลตามชื่อ ==========
def stream_response_by_model(model_name, messages, stream_output):
    """
    รองรับการเรียกโมเดลทั้ง GPT (OpenAI) และ LLM Local (Ollama)
    """
    reply = ""
    # ========== กรณีใช้ GPT ==========
    if model_name.startswith("gpt-"):
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        response = client.chat.completions.create(
            model=model_name,
            messages=messages,
            stream=True,
        )
        for chunk in response:
            if chunk.choices and chunk.choices[0].delta.content:
                word = chunk.choices[0].delta.content
                reply += word
                stream_output.markdown(reply + "▌", unsafe_allow_html=True)
    # ========== กรณีใช้ LLaMA2 (ผ่าน Ollama) ==========
    elif model_name.startswith(("llama", "mistral", "phi")) or model_name.endswith(
        ":latest"
    ):
        # กรณีใช้ผ่าน Ollama
        full_prompt = (
            "\n".join([f"{m['role']}: {m['content']}" for m in messages])
            + "\nassistant:"
        )
        res = requests.post(
            "http://localhost:11434/api/generate",
            json={"model": model_name, "prompt": full_prompt, "stream": True},
            stream=True,
        )
        for line in res.iter_lines():
            if line:
                chunk = json.loads(line.decode("utf-8"))
                if "response" in chunk:
                    word = chunk["response"]
                    reply += word
                    stream_output.markdown(reply + "▌", unsafe_allow_html=True)

    else:
        stream_output.markdown("❌ ไม่รองรับโมเดลนี้")

    return reply
