import sqlite3
import os

DB = r"C:\Users\souvi\OneDrive\Desktop\civic_ai_backend\civic_ai.db"

print("DB exists:", os.path.exists(DB))

conn = sqlite3.connect(DB)
tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()

print("Tables:", tables)
conn.close()