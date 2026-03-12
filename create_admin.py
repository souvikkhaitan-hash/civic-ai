from database import get_connection

conn = get_connection()
cur = conn.cursor()

cur.execute("""
INSERT INTO admins (username, password)
VALUES (?, ?)
""", ("admin", "admin123"))

conn.commit()
conn.close()

print("✅ Admin created")