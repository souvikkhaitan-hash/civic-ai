import sqlite3

conn = sqlite3.connect("civic_ai.db")
cur = conn.cursor()

try:
    cur.execute("ALTER TABLE complaints ADD COLUMN previous_status TEXT")
    print("✅ Column added successfully")
except Exception as e:
    print("⚠️ Maybe already exists:", e)

conn.commit()
conn.close()