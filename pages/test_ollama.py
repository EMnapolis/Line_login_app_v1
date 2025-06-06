from utility_ai import *

# ========== ตั้งค่า ==========
st.title("🤖 สนทนากับ AI พร้อมใช้งานไฟล์และเลือกโมเดลได้")

# เลือกโมเดล
model_choice = st.radio("🧠 เลือกโมเดลที่ต้องการใช้", ["gpt-4o", "llama2:latest"], horizontal=True)

# อัปโหลดไฟล์
uploaded_file = st.file_uploader("📂 อัปโหลดไฟล์ (txt, csv, xlsx)", type=["txt", "csv", "xlsx"])
if uploaded_file:
    try:
        file_content = read_uploaded_file(uploaded_file.name, uploaded_file)
        st.session_state["file_text"] = file_content
        st.text_area("📄 ตัวอย่างเนื้อหาไฟล์", file_content[:1000], height=200, disabled=True)
    except Exception as e:
        st.error(f"❌ ไม่สามารถอ่านไฟล์ได้: {e}")
        st.stop()

# ค่าเริ่มต้น
file_content = st.session_state.get("file_text", "")
st.session_state.setdefault("chat_all_in_one", [])

# แสดงบทสนทนาย้อนหลัง
for msg in st.session_state["chat_all_in_one"]:
    st.chat_message(msg["role"]).write(msg["content"])

# ช่องพิมพ์คำถาม
if prompt := st.chat_input("พิมพ์คำถามของคุณ (หรือพิมพ์ว่า 'ขอไฟล์')"):
    st.chat_message("user").write(prompt)
    st.session_state["chat_all_in_one"].append({"role": "user", "content": prompt})

    if prompt.strip() == "ขอไฟล์" or (
        "save" in prompt.lower() and st.session_state.get("analysis_result")
    ):
        st.chat_message("assistant").write("📦 คลิกด้านล่างเพื่อดาวน์โหลดไฟล์")
        st.session_state["show_download"] = True
    else:
        try:
            base_messages = [
                {
                    "role": "system",
                    "content": "คุณคือผู้ช่วยที่สามารถตอบคำถามทั่วไป และใช้เนื้อหาจากไฟล์หากมี",
                }
            ]
            if file_content:
                base_messages.append(
                    {"role": "user", "content": f"เนื้อหาในไฟล์ทั้งหมด:\n{file_content}"}
                )
            base_messages.extend(st.session_state["chat_all_in_one"])

            with st.chat_message("assistant"):
                stream_output = st.empty()
                reply = stream_response_by_model(model_choice, base_messages, stream_output)
                stream_output.markdown(reply)

            # เก็บข้อความตอบกลับและใช้สำหรับดาวน์โหลด
            st.session_state["chat_all_in_one"].append({"role": "assistant", "content": reply})
            st.session_state["analysis_result"] = reply
            st.session_state["show_download"] = False

            # นับ tokens
            prompt_tokens = sum(count_tokens(m["content"]) for m in base_messages)
            completion_tokens = count_tokens(reply)
            total_tokens = prompt_tokens + completion_tokens

            st.session_state["messages_gpt"] = base_messages + [
                {
                    "role": "assistant",
                    "content": reply,
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": total_tokens,
                    "response_json": "{}",
                }
            ]
            # บันทึก SQLite
            save_conversation_if_ready(
                conn,
                cursor,
                messages_key="messages_gpt",
                source="chat_gpt",
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
            )

        except Exception as e:
            st.error(f"❌ Error: {e}")

# ปุ่มดาวน์โหลดผลลัพธ์
show_download_section()

