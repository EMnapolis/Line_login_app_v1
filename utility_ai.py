# utility_ai.py
import json
import os
import requests
import subprocess
from utility_chat import *

# Initialize SQLite connection
conn, cursor = init_db()
initialize_schema(conn)

# ===== API / Auth configuration =====
CHANNEL_ID = os.getenv("CHANNEL_ID")
CHANNEL_SECRET = os.getenv("CHANNEL_SECRET")
REDIRECT_URI = os.getenv("REDIRECT_URI")
STATE = os.getenv("STATE")
CHAT_TOKEN = os.getenv("CHAT_TOKEN")

# Logging configuration
ACCESS_LOG_FILE = os.getenv("ACCESS_LOG_FILE", "access_log.txt")

# AI Keys configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")  # Ensure environment variable is set
OLLAMA_SERVER_URL = os.getenv("OLLAMA_SERVER_URL")


# ===== Function to count tokens =====
def count_tokens(text, model="gpt-4o"):
    """
    Counts the number of tokens in a given text for a specified model.
    """
    try:
        encoding = tiktoken.encoding_for_model(model)
    except Exception:
        encoding = tiktoken.get_encoding("cl100k_base")
    return len(encoding.encode(text))


def estimate_tokens(text: str, model: str = None) -> int:
    """
    Estimates the number of tokens based on the number of words in the text.
    """
    words = len(text.split())
    return int(words / 0.75)


# ===== Function to parse LLaMA stream response =====
def parse_llama_stream_response(res):
    """
    Parse and decode a JSON stream response from LLaMA.
    """
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
            except Exception as e:
                print("❌ Error decoding JSON chunk:", e)
                continue

    return reply, {"chunks": raw_chunks, "full_reply": reply}


# ===== Function to stream responses based on model =====
def stream_response_by_model(model_name, messages, stream_output):
    """
    Streams responses from models like GPT (OpenAI) or Ollama based on the model name.
    """
    reply = ""
    raw_json = {}
    prompt_tokens = 0
    completion_tokens = 0
    total_tokens = 0

    # ===== GPT Models Response =====
    if model_name.startswith("gpt-"):
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        response = client.chat.completions.create(
            model=model_name,
            messages=messages,
            stream=True,
        )

        # Stream the response
        chunks = []
        for chunk in response:
            if st.session_state.get("stop_chat", False):
                stream_output.markdown("🛑 Stopped displaying.")
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

    # ===== OLLAMA Models Response =====
    else:
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

            # Stream and parse the response
            reply, raw_chunks = parse_llama_stream_response(res)
            reply += parse_llama_stream_response(res)
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
            stream_output.markdown(f"❌ Unable to connect to Ollama: {e}")
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


# ===== Function to get list of available Ollama models =====
def get_ollama_models():
    """
    Fetches the list of available models from the Ollama server.
    """
    try:
        response = requests.get(f"{OLLAMA_SERVER_URL}/api/tags")
        response.raise_for_status()
        data = response.json()
        return [m["name"] for m in data.get("models", [])]
    except Exception as e:
        print(f"❌ Unable to fetch model list from Ollama: {e}")
        return []


# ===== Display AI response information =====
def display_ai_response_info(model_choice, base_messages, stream_output):
    """
    Calls the model and displays its response along with token usage, model, and the time taken.
    """
    start_time = time.time()
    result = stream_response_by_model(model_choice, base_messages, stream_output)
    end_time = time.time()
    duration = round(end_time - start_time, 2)

    reply = result["reply"]
    stream_output.markdown(reply)

    st.caption(
        f"📌 Model used: `{model_choice}` | "
        f"Tokens: Prompt = {result['prompt_tokens']}, Completion = {result['completion_tokens']}, "
        f"Total = {result['total_tokens']} | "
        f"⏱️ Time taken: {duration} seconds"
    )

    return result


# ===== Function to check token quota =====
def check_token_quota():
    """
    Checks the user's token usage and warns if nearing the limit.
    """
    from utility_chat import init_db

    conn, cursor = init_db()
    current_user = st.session_state.get("user_id", "")
    role = st.session_state.get("role", "").lower()

    # Fetch total token usage
    cursor.execute(
        """
        SELECT SUM(total_tokens) FROM token_usage
        WHERE user_id = ?
    """,
        (current_user,),
    )
    used_token = cursor.fetchone()[0] or 0

    # Fetch latest quota override from DB
    cursor.execute(
        """
        SELECT quota_override FROM token_usage
        WHERE user_id = ? AND quota_override IS NOT NULL
        ORDER BY id DESC LIMIT 1
    """,
        (current_user,),
    )
    quota_row = cursor.fetchone()
    quota_limit = quota_row[0] if quota_row else 1_000_000  # Default Quota Fallback

    # Calculate used percentage
    percent_used = round((used_token / quota_limit) * 100, 2)

    # Warn when usage exceeds 90%
    if percent_used >= 90 and used_token < quota_limit:
        st.warning(
            f"⚠️ You have used {percent_used}% of your tokens.\n"
            f"🔢 Usage: `{used_token:,}` out of `{quota_limit:,}` tokens.\n"
            f"🧭 Please plan your usage accordingly."
        )

    # Stop usage if quota exceeded
    if used_token >= quota_limit and role not in ["admin", "super admin"]:
        st.error(
            f"❌ You have exceeded your token quota.\n"
            f"🔢 Usage: `{used_token:,}` out of `{quota_limit:,}` tokens.\n"
            f"🛑 Please contact your administrator to request additional quota or wait for the next cycle."
        )
        st.stop()
