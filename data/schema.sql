-- ===========================================
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
    Role TEXT,                                              -- บทบาท เช่น admin, user
    updated_at TEXT NOT NULL                                -- เวลาที่ข้อมูลถูกอัปเดตล่าสุด
);

-- ===========================================
-- Table: conversations
-- เก็บข้อมูล "หัวข้อบทสนทนา" ระหว่างระบบกับผู้ใช้
-- เป็น master table ที่เชื่อมไปยัง messages
-- ===========================================
CREATE TABLE IF NOT EXISTS conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,                   -- รหัสบทสนทนา (Auto Increment)
    user_id TEXT NOT NULL,                                  -- รหัสผู้ใช้เจ้าของบทสนทนา
    name TEXT NOT NULL,                                     -- ชื่อหรือหัวข้อของบทสนทนา
    source TEXT,                                            -- แหล่งที่มาของการสนทนา เช่น chat_gpt, line_bot
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP          -- เวลาที่สร้างบทสนทนา
);

-- ===========================================
-- Table: messages
-- เก็บข้อความในแต่ละบทสนทนา (ข้อความระหว่าง user กับ AI)
-- ใช้เชื่อมกับ table conversations
-- ===========================================
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,                   -- รหัสข้อความแต่ละบรรทัด
    user_id TEXT NOT NULL,                                  -- รหัสผู้ใช้ที่เป็นเจ้าของข้อความ
    conversation_id INTEGER,                                -- รหัสบทสนทนาที่ข้อความนี้สังกัด
    role TEXT,                                              -- บทบาท: user, assistant, system
    content TEXT,                                           -- เนื้อหาข้อความ
    total_tokens INTEGER,                                   -- จำนวน token ที่ข้อความนี้ใช้ (สำหรับวิเคราะห์ cost)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,         -- เวลาที่ข้อความถูกบันทึก
    FOREIGN KEY(conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
);

-- ===========================================
-- Table: prompts
-- สำหรับเก็บข้อความ prompt (คำสั่ง หรือ system message)
-- ที่ต้องใช้ซ้ำ เช่น “สรุปข้อความ”, “โครงเรื่อง”
CREATE TABLE IF NOT EXISTS prompts (
    name TEXT,
    user_id TEXT NOT NULL,
    content TEXT,
    PRIMARY KEY (name, user_id)
);

-- ===========================================
-- Table: sent_records
-- ใช้เก็บ record ที่เคย "ส่งออก" ไปแล้ว เช่นส่งไป LINE Notify
-- เพื่อป้องกันการส่งซ้ำ
-- ===========================================
CREATE TABLE IF NOT EXISTS sent_records (
    recId TEXT PRIMARY KEY                                   -- รหัสข้อมูลที่เคยถูกส่งออกแล้ว
);