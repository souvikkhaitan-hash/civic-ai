import sqlite3
import json

DB_NAME = "civic_ai.db"

def get_connection():
    return sqlite3.connect(DB_NAME)

# ==============================
# INIT DATABASE
# ==============================
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
        previous_status TEXT,
        user_id INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_updated_at TIMESTAMP,
        master_id INTEGER DEFAULT NULL,
        is_duplicate INTEGER DEFAULT 0
    )
    """)

    conn.commit()
    conn.close()

# ==============================
# DUPLICATE MASTER
# ==============================
def find_duplicate_master(text):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT id FROM complaints
        WHERE complaint = ?
        AND is_duplicate = 0
        LIMIT 1
    """, (text,))

    row = cur.fetchone()
    conn.close()
    return row[0] if row else None

# ==============================
# SAVE COMPLAINT
# ==============================
def save_complaint(text, dept, priority, risk, explanation, user_id):
    conn = get_connection()
    cur = conn.cursor()

    master_id = find_duplicate_master(text)

    if master_id:
        cur.execute("""
            INSERT INTO complaints
            (complaint, department, priority, risk_score, user_id, master_id, is_duplicate)
            VALUES (?, ?, ?, ?, ?, ?, 1)
        """, (text, dept, priority, risk, user_id, master_id))
    else:
        cur.execute("""
            INSERT INTO complaints
            (complaint, department, priority, risk_score, explanation, user_id)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (text, dept, priority, risk, json.dumps(explanation), user_id))

    conn.commit()
    conn.close()

# ==============================
# AI SUPPORT FUNCTIONS
# ==============================
def find_similar_open_complaint(keyword):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, risk_score, explanation
        FROM complaints
        WHERE complaint LIKE ?
        AND status IN ('OPEN','IN_PROGRESS')
        ORDER BY created_at DESC
        LIMIT 1
    """, (f"%{keyword}%",))

    row = cur.fetchone()
    conn.close()
    return row

def escalate_complaint(complaint_id, new_score, explanation):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        UPDATE complaints
        SET risk_score=?,
            explanation=?,
            status='IN_PROGRESS',
            last_updated_at=CURRENT_TIMESTAMP
        WHERE id=?
    """, (new_score, json.dumps(explanation), complaint_id))

    conn.commit()
    conn.close()

# ==============================
# STATUS ENGINE
# ==============================
def update_status(complaint_id, new_status):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        UPDATE complaints
        SET previous_status=status,
            status=?
        WHERE id=? OR master_id=?
    """, (new_status, complaint_id, complaint_id))

    conn.commit()
    conn.close()

def undo_status(complaint_id):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        UPDATE complaints
        SET status=previous_status
        WHERE id=? OR master_id=?
    """, (complaint_id, complaint_id))

    conn.commit()
    conn.close()

# ==============================
# DELETE
# ==============================
def delete_complaint(complaint_id):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        DELETE FROM complaints
        WHERE id=? OR master_id=?
    """, (complaint_id, complaint_id))

    conn.commit()
    conn.close()

# ==============================
# SLA ENGINE (THIS WAS MISSING ❗)
# ==============================
def enforce_sla():
    conn = get_connection()
    cur = conn.cursor()

    # OPEN → IN_PROGRESS after 24h
    cur.execute("""
        UPDATE complaints
        SET status='IN_PROGRESS'
        WHERE status='OPEN'
        AND datetime(created_at) <= datetime('now','-24 hours')
    """)

    # escalate priority
    cur.execute("""
        UPDATE complaints
        SET priority='HIGH'
        WHERE status='IN_PROGRESS'
        AND datetime(created_at) <= datetime('now','-48 hours')
    """)

    conn.commit()
    conn.close()

# ==============================
# ADMIN DASHBOARD
# ==============================
def get_all_complaints():
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("""
        SELECT 
            c.id,
            c.complaint,
            c.department,
            c.priority,
            c.status,
            c.risk_score,
            c.created_at,
            COUNT(d.id)+1 as count
        FROM complaints c
        LEFT JOIN complaints d ON d.master_id=c.id
        WHERE c.is_duplicate=0
        GROUP BY c.id
        ORDER BY c.created_at DESC
    """)

    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows

# ==============================
# USER DASHBOARD (ALSO MISSING)
# ==============================
def get_user_complaints(user_id):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, complaint, department, priority, status, risk_score, created_at
        FROM complaints
        WHERE user_id=?
        ORDER BY created_at DESC
    """, (user_id,))

    rows = cur.fetchall()
    conn.close()

    return [
        {
            "id": r[0],
            "complaint": r[1],
            "department": r[2],
            "priority": r[3],
            "status": r[4],
            "risk_score": r[5],
            "created_at": r[6]
        }
        for r in rows
    ]

# ==============================
# ANALYTICS
# ==============================
def get_analytics():
    conn = get_connection()
    cur = conn.cursor()

    data = {}
    cur.execute("SELECT COUNT(*) FROM complaints")
    data["total"] = cur.fetchone()[0]

    cur.execute("SELECT status, COUNT(*) FROM complaints GROUP BY status")
    data["status"] = dict(cur.fetchall())

    conn.close()
    return data