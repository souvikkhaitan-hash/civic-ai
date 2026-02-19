import sqlite3
import json

DB_NAME = "civic_ai.db"

def get_connection():
    return sqlite3.connect(DB_NAME)

def init_db():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS complaints (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        complaint TEXT NOT NULL,
        department TEXT NOT NULL,
        priority TEXT NOT NULL,
        risk_score INTEGER NOT NULL,
        explanation TEXT,
        status TEXT DEFAULT 'OPEN',
        user_id INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
       # ==============================
    # USERS TABLE
    # ==============================
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # ==============================
    # OFFICERS TABLE
    # ==============================
    cur.execute("""
    CREATE TABLE IF NOT EXISTS officers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        department TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)


    conn.commit()
    conn.close()


# ✅ SINGLE SOURCE OF TRUTH (SAVE)
def save_complaint(complaint, department, priority, risk_score, explanation, user_id):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO complaints
        (complaint, department, priority, risk_score, explanation, user_id)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        complaint,
        department,
        priority,
        risk_score,
        json.dumps(explanation),
        user_id
    ))

    conn.commit()
    conn.close()


# 🔁 FIND SIMILAR OPEN / IN_PROGRESS COMPLAINT
def find_similar_open_complaint(keyword):
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("""
        SELECT id, risk_score, explanation
        FROM complaints
        WHERE complaint LIKE ?
        AND status IN ('OPEN', 'IN_PROGRESS')
        ORDER BY created_at DESC
        LIMIT 1
    """, (f"%{keyword}%",))

    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


# 🔥 ESCALATE EXISTING COMPLAINT (DUPLICATE MERGE)
def escalate_complaint(complaint_id, new_score, explanation):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        UPDATE complaints
        SET risk_score = ?,
            explanation = ?,
            status = 'IN_PROGRESS'
        WHERE id = ?
    """, (
        new_score,
        json.dumps(explanation),
        complaint_id
    ))

    conn.commit()
    conn.close()


def update_status(complaint_id, new_status):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        UPDATE complaints
        SET previous_status = status,
            status = ?,
            last_updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (new_status, complaint_id))

    conn.commit()
    conn.close()

def undo_status(complaint_id):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        UPDATE complaints
        SET status = previous_status,
            last_updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (complaint_id,))

    conn.commit()
    conn.close()


def enforce_sla():
    conn = get_connection()
    cur = conn.cursor()

    # OPEN > 24 hours
    cur.execute("""
        UPDATE complaints
        SET status = 'IN_PROGRESS'
        WHERE status = 'OPEN'
        AND datetime(created_at) <= datetime('now', '-24 hours')
    """)

    # IN_PROGRESS > 48 hours → HIGH
    cur.execute("""
        UPDATE complaints
        SET priority = 'HIGH'
        WHERE status = 'IN_PROGRESS'
        AND datetime(created_at) <= datetime('now', '-48 hours')
    """)

    conn.commit()
    conn.close()

def get_analytics():
    conn = get_connection()
    cur = conn.cursor()

    analytics = {}

    cur.execute("SELECT COUNT(*) FROM complaints")
    analytics["total"] = cur.fetchone()[0]

    cur.execute("SELECT status, COUNT(*) FROM complaints GROUP BY status")
    analytics["by_status"] = dict(cur.fetchall())

    cur.execute("SELECT department, COUNT(*) FROM complaints GROUP BY department")
    analytics["by_department"] = dict(cur.fetchall())

    cur.execute("SELECT COUNT(*) FROM complaints WHERE priority = 'HIGH'")
    analytics["high_priority"] = cur.fetchone()[0]

    conn.close()
    return analytics



def get_all_complaints():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, complaint, department, priority,
               risk_score, explanation, status, created_at
        FROM complaints
        ORDER BY created_at DESC
    """)

    rows = cur.fetchall()
    conn.close()

    complaints = []
    for row in rows:
        complaints.append({
            "id": row[0],
            "complaint": row[1],
            "department": row[2],
            "priority": row[3],
            "risk_score": row[4],
            "explanation": json.loads(row[5]) if row[5] else [],
            "status": row[6],
            "created_at": row[7]
        })

    return complaints

def get_user_complaints(user_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, complaint, department, priority, status, risk_score, created_at
        FROM complaints
        WHERE user_id = ?
        ORDER BY created_at DESC
    """, (user_id,))

    rows = cursor.fetchall()
    conn.close()

    complaints = []
    for row in rows:
        complaints.append({
            "id": row[0],
            "complaint": row[1],
            "department": row[2],
            "priority": row[3],
            "status": row[4],
            "risk_score": row[5],
            "created_at": row[6]
        })

    return complaints

def get_user_dashboard(user_id):
    conn = get_connection()
    cur = conn.cursor()

    # total complaints
    cur.execute("SELECT COUNT(*) FROM complaints WHERE user_id = ?", (user_id,))
    total = cur.fetchone()[0]

    # status counts
    cur.execute("""
        SELECT status, COUNT(*) 
        FROM complaints 
        WHERE user_id = ?
        GROUP BY status
    """, (user_id,))
    status_counts = dict(cur.fetchall())

    conn.close()

    return {
        "total": total,
        "status_counts": status_counts
    }