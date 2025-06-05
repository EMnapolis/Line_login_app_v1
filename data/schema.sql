-- ============== schema.sql =================
-- Table: access_login
-- ใช้เก็บข้อมูลผู้ใช้ที่ขอเข้าระบบ เช่น LINE Login
-- ตรวจสอบสิทธิ์การเข้าถึง และสถานะอนุมัติ
-- ===========================================
CREATE TABLE IF NOT EXISTS access_login (
    user_id TEXT PRIMARY KEY,                               -- รหัสประจำตัวผู้ใช้ (LINE user ID)
    display_name TEXT NOT NULL,                             -- ชื่อแสดง
    picture_url TEXT NULL,                                  -- URL รูปโปรไฟล์ (ถ้ามี)
    status TEXT CHECK(status IN ('PENDING','DENIED','APPROVED')) NOT NULL DEFAULT 'PENDING', 
                                                            -- สถานะการอนุมัติ: รอดำเนินการ / ปฏิเสธ / อนุมัติ
    Role TEXT,                                              -- บทบาท เช่น super admin , admin, user
    updated_at TEXT NOT NULL                                -- เวลาที่ข้อมูลถูกอัปเดตล่าสุด
);

-- ===========================================
-- Table: conversations
-- เก็บข้อมูล "หัวข้อบทสนทนา" ระหว่างระบบกับผู้ใช้
-- เป็น master table ที่เชื่อมไปยัง messages
-- ===========================================
-- สร้างตาราง conversations สำหรับเก็บบทสนทนาแต่ละชุด
CREATE TABLE IF NOT EXISTS conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,           -- รหัสบทสนทนา
    user_id TEXT NOT NULL,                          -- รหัสผู้ใช้
    title TEXT,                                     -- ชื่อบทสนทนา (เพิ่มใหม่)
    source TEXT,                                    -- แหล่งที่มา เช่น 'chat_gpt' หรืออื่นๆ
    prompt_tokens INTEGER,                          -- จำนวน token ของ prompt
    completion_tokens INTEGER,                      -- จำนวน token ของคำตอบที่ AI สร้าง
    total_tokens INTEGER,                           -- token รวมของข้อความนี้
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP  -- เวลาที่สร้างบทสนทนา
);

-- สร้างตาราง messages สำหรับเก็บข้อความในแต่ละบทสนทนา
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,           -- รหัสของข้อความแต่ละรายการ
    user_id TEXT NOT NULL,                          -- รหัสของผู้ใช้เจ้าของข้อความ
    conversation_id INTEGER,                        -- รหัสบทสนทนาที่ข้อความนี้อยู่
    role TEXT,                                      -- บทบาทของข้อความ: user, assistant, system
    content TEXT,                                   -- เนื้อหาของข้อความ
    prompt_tokens INTEGER,                          -- จำนวน token ของ prompt
    completion_tokens INTEGER,                      -- จำนวน token ของคำตอบที่ AI สร้าง
    total_tokens INTEGER,                           -- token รวมของข้อความนี้
    response_json TEXT,                             -- ✅ เก็บ JSON ทั้ง body ที่ได้จาก GPT API
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, -- เวลาที่บันทึกข้อความนี้
    FOREIGN KEY(conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
);

-- สร้างตาราง prompts สำหรับเก็บ Prompt ที่ผู้ใช้สร้างขึ้นเอง
CREATE TABLE IF NOT EXISTS prompts (
    prompt_name TEXT,                             -- ชื่อเรียกของ prompt (ตั้งเองได้)
    user_id TEXT NOT NULL,                        -- รหัสของผู้ใช้ที่สร้าง prompt
    content TEXT,                                 -- เนื้อหา prompt
    prompt_tokens INTEGER,                        -- token ที่ใช้สำหรับ prompt
    completion_tokens INTEGER,                    -- token ที่ใช้สำหรับคำตอบจาก AI
    total_tokens INTEGER,                         -- token รวมทั้งหมด
    PRIMARY KEY (prompt_name, user_id)            -- ป้องกันชื่อ prompt ซ้ำกันในผู้ใช้คนเดียวกัน
);

-- ===========================================
-- Table: raw_json
-- ใช้เก็บ JSON ต้นฉบับจาก GPT API แบบเต็ม
-- ===========================================
CREATE TABLE IF NOT EXISTS raw_json (
    id INTEGER PRIMARY KEY AUTOINCREMENT,            -- รหัสอัตโนมัติ
    conversation_id INTEGER,                         -- รหัสบทสนทนา (อ้างอิงถึง conversations.id)
    message_id INTEGER NOT NULL,                     -- รหัสข้อความ (อ้างอิงถึง messages.id)
    response_json TEXT NOT NULL,                     -- JSON ต้นฉบับจาก GPT API
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,  -- เวลาที่เก็บ JSON นี้
    FOREIGN KEY(conversation_id) REFERENCES conversations(id) ON DELETE CASCADE,
    FOREIGN KEY(message_id) REFERENCES messages(id) ON DELETE CASCADE
);

-- ===========================================
-- Table: sent_records
-- ใช้เก็บ record ที่เคย "ส่งออก" ไปแล้ว เช่นส่งไป LINE Notify
-- เพื่อป้องกันการส่งซ้ำ
-- ===========================================
CREATE TABLE IF NOT EXISTS sent_records (
    recId TEXT PRIMARY KEY                                   -- รหัสข้อมูลที่เคยถูกส่งออกแล้ว
);