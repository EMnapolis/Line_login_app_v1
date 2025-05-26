--schema.sql

-- Table: access_login
CREATE TABLE IF NOT EXISTS access_login (
    user_id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    picture_url TEXT NULL,
    status TEXT CHECK(status IN ('PENDING','DENIED', 'APPROVED')) NOT NULL DEFAULT 'PENDING',
    updated_at TEXT NOT NULL
);

-- Table: sent_records
CREATE TABLE IF NOT EXISTS sent_records (
    recId TEXT PRIMARY KEY
);

-- -- Table: user_role_assignments
-- CREATE TABLE IF NOT EXISTS user_role_assignments (
--     user_id TEXT NO_
