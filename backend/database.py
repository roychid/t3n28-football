import sqlite3, os
from datetime import datetime

DB_PATH = os.environ.get("DB_PATH", "t3n28.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn

def init_db():
    db = get_db()
    c  = db.cursor()

    c.execute("""CREATE TABLE IF NOT EXISTS users (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        email         TEXT UNIQUE NOT NULL,
        name          TEXT NOT NULL DEFAULT '',
        whatsapp      TEXT DEFAULT '',
        password_hash TEXT NOT NULL,
        tier          TEXT NOT NULL DEFAULT 'free',
        status        TEXT NOT NULL DEFAULT 'active',
        created_at    TEXT NOT NULL DEFAULT (datetime('now')),
        last_login    TEXT
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS sub_requests (
        id             INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id        INTEGER NOT NULL REFERENCES users(id),
        email          TEXT NOT NULL,
        name           TEXT DEFAULT '',
        whatsapp       TEXT DEFAULT '',
        requested_tier TEXT NOT NULL,
        status         TEXT NOT NULL DEFAULT 'pending',
        admin_note     TEXT DEFAULT '',
        created_at     TEXT NOT NULL DEFAULT (datetime('now')),
        resolved_at    TEXT
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS api_usage (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id     INTEGER NOT NULL REFERENCES users(id),
        email       TEXT NOT NULL,
        tier        TEXT NOT NULL,
        date        TEXT NOT NULL,
        count       INTEGER NOT NULL DEFAULT 0,
        cache_hits  INTEGER NOT NULL DEFAULT 0,
        real_calls  INTEGER NOT NULL DEFAULT 0,
        last_call   TEXT,
        UNIQUE(user_id, date)
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS api_cache (
        cache_key   TEXT PRIMARY KEY,
        endpoint    TEXT NOT NULL,
        response    TEXT NOT NULL,
        fetched_at  TEXT NOT NULL DEFAULT (datetime('now')),
        fetched_by  INTEGER,
        fetched_tier TEXT
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS api_daily_total (
        date        TEXT PRIMARY KEY,
        total       INTEGER DEFAULT 0,
        cache_hits  INTEGER DEFAULT 0,
        real_calls  INTEGER DEFAULT 0
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS tier_changes (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id     INTEGER NOT NULL REFERENCES users(id),
        old_tier    TEXT,
        new_tier    TEXT NOT NULL,
        changed_by  TEXT NOT NULL,
        note        TEXT DEFAULT '',
        changed_at  TEXT NOT NULL DEFAULT (datetime('now'))
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS notifications (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id     INTEGER NOT NULL REFERENCES users(id),
        type        TEXT NOT NULL,
        message     TEXT NOT NULL,
        read        INTEGER NOT NULL DEFAULT 0,
        created_at  TEXT NOT NULL DEFAULT (datetime('now'))
    )""")

    db.commit()
    db.close()
    print("✅ DB ready")

def row_to_dict(row):
    return dict(row) if row else None

def rows_to_list(rows):
    return [dict(r) for r in rows]
