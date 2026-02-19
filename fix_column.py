from database import get_connection

conn = get_connection()
cur = conn.cursor()

cur.execute("ALTER TABLE complaints ADD COLUMN user_id INTEGER")

conn.commit()
conn.close()

print("✅ user_id column added!")