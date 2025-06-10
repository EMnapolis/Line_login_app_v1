# utility_ai.py
from utility_chat import *
import requests

# เชื่อมต่อ SQLite
conn, cursor = init_db()
initialize_schema(conn)
# ==== AI KEY ====
llama_server = os.getenv("OLLAMA_SERVER_URL")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY)

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
    รองรับ GPT (OpenAI) และ LLM Local (เช่น LLaMA ผ่าน Ollama)
    คืนค่า dict พร้อมข้อมูลบทสนทนาและ token usage
    """
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

        chunks = []
        for chunk in response:
            chunks.append(chunk.model_dump())
            if chunk.choices and chunk.choices[0].delta.content:
                word = chunk.choices[0].delta.content
                reply += word
                stream_output.markdown(reply + "▌", unsafe_allow_html=True)

        stream_output.markdown(reply)

        raw_json = {
            "model": model_name,
            "chunks": chunks,
            "full_reply": reply,
        }

        prompt_tokens = sum(
            count_tokens(m["content"], model=model_name) for m in messages
        )
        completion_tokens = count_tokens(reply, model=model_name)
        total_tokens = prompt_tokens + completion_tokens

    elif model_name.startswith(
        ("llama", "mistral", "phi", "gemma")
    ) or model_name.endswith(":latest"):
        llama_server = (
            os.getenv("OLLAMA_SERVER_URL") or "http://localhost:11434/api/generate"
        )  # ✅ ปลอดภัย fallback
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
