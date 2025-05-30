--schema.sql

-- Table: access_login
CREATE TABLE IF NOT EXISTS access_login (
    user_id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    picture_url TEXT NULL,
    status TEXT CHECK(status IN ('PENDING','DENIED', 'APPROVED')) NOT NULL DEFAULT 'PENDING',
    Role TEXT,
    updated_at TEXT NOT NULL
);

-- Table: sent_records
CREATE TABLE IF NOT EXISTS sent_records (
    recId TEXT PRIMARY KEY
);

-- Table: conversations
CREATE TABLE IF NOT EXISTS conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    name TEXT NOT NULL,
    source TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Table: messages
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER,
    role TEXT,
    content TEXT,
    total_tokens INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(conversation_id) REFERENCES conversations(id)
);

-- Table: prompts
CREATE TABLE IF NOT EXISTS prompts (
    name TEXT PRIMARY KEY,
    content TEXT
);

-- Table: sent_records (สำรองใช้สำหรับบันทึก ID ที่ส่งออก)
CREATE TABLE IF NOT EXISTS sent_records (
    recId TEXT PRIMARY KEY
);