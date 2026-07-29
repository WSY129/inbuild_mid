import sqlite3

def init_db():
    conn = sqlite3.connect("blood_link.db")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT UNIQUE,
            password TEXT,
            nickname TEXT,
            blood_type_abo TEXT,
            rh_type TEXT,
            birth_date TEXT,
            last_donation_date TEXT,
            last_donation_method TEXT,
            notification_agreed INTEGER
        )
    """)
    conn.commit()
    conn.close()