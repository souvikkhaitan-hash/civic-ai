import sqlite3
import json
from utils.similarity import is_similar
import os
from sentence_transformers import SentenceTransformer, util
from datetime import datetime
import ai_agent

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_NAME = os.path.join(BASE_DIR, "civic_ai.db")
print("[DB] USING DB:", DB_NAME)

def get_connection():
    conn = sqlite3.connect(DB_NAME, timeout=20)
    conn.execute("PRAGMA journal_mode=WAL") # Enable WAL mode
    conn.row_factory = sqlite3.Row
    return conn

# ==============================
# INIT DATABASE
# ==============================
def init_db():
    conn = get_connection()
    cur = conn.cursor()

    # ======================
    # COMPLAINTS TABLE
    # ======================
    cur.execute("""
    CREATE TABLE IF NOT EXISTS complaints (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        complaint TEXT NOT NULL,
        department TEXT NOT NULL,
        priority TEXT NOT NULL,
        risk_score INTEGER NOT NULL,
        latitude REAL,
        longitude REAL,
        manual_location TEXT,
        explanation TEXT,
        status TEXT DEFAULT 'OPEN',
        previous_status TEXT,
        user_id INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_updated_at TIMESTAMP,
        master_id INTEGER DEFAULT NULL,
        is_duplicate INTEGER DEFAULT 0,
        image_path TEXT DEFAULT NULL,
        address TEXT DEFAULT NULL,
        state TEXT DEFAULT 'Unknown',
        city TEXT DEFAULT 'Unknown',
        area TEXT DEFAULT 'Unknown',
        source TEXT DEFAULT 'user',
        assigned_officer TEXT DEFAULT 'Panchayat Officer',
        translated_text TEXT,
        mobile TEXT DEFAULT NULL
    )
    """)

    # --- MIGRATION: Add image_path if missing ---
    try:
        cur.execute("ALTER TABLE complaints ADD COLUMN image_path TEXT DEFAULT NULL")
    except sqlite3.OperationalError:
        pass # Already exists

    # --- MIGRATION: Add address if missing ---
    try:
        cur.execute("ALTER TABLE complaints ADD COLUMN address TEXT DEFAULT NULL")
    except sqlite3.OperationalError:
        pass # Already exists

    # --- MIGRATION: Add source if missing ---
    try:
        cur.execute("ALTER TABLE complaints ADD COLUMN source TEXT DEFAULT 'user'")
    except sqlite3.OperationalError:
        pass # Already exists

    # --- MIGRATION: Add state/city/area if missing ---
    for col in ["state", "city", "area"]:
        try:
            cur.execute(f"ALTER TABLE complaints ADD COLUMN {col} TEXT DEFAULT 'Unknown'")
        except sqlite3.OperationalError:
            pass

    # --- MIGRATION: Add assigned_officer if missing ---
    try:
        cur.execute("ALTER TABLE complaints ADD COLUMN assigned_officer TEXT")
    except sqlite3.OperationalError:
        pass

    # --- MIGRATION: Add translated_text if missing ---
    try:
        cur.execute("ALTER TABLE complaints ADD COLUMN translated_text TEXT")
    except sqlite3.OperationalError:
        pass

    # --- MIGRATION: Add mobile if missing ---
    try:
        cur.execute("ALTER TABLE complaints ADD COLUMN mobile TEXT")
    except sqlite3.OperationalError:
        pass

    # --- MIGRATION: Add hidden flags for role-based deletion ---
    try:
        cur.execute("ALTER TABLE complaints ADD COLUMN hidden_from_admin INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass

    try:
        cur.execute("ALTER TABLE complaints ADD COLUMN hidden_from_officer INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass

    # --- MIGRATION: Add notifications table ---
    cur.execute("""
    CREATE TABLE IF NOT EXISTS notifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        officer_id INTEGER,
        message TEXT,
        type TEXT,
        is_read INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # --- MIGRATION: Add location_source if missing ---
    try:
        cur.execute("ALTER TABLE complaints ADD COLUMN location_source TEXT")
    except sqlite3.OperationalError:
        pass

    # ======================
    # USERS TABLE
    # ======================
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # ======================
    # OFFICERS TABLE
    # ======================
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

    # --- SEED OFFICERS ---
    cur.execute("SELECT COUNT(*) FROM officers")
    count = cur.fetchone()[0]
    if count == 0:
        cur.execute("""
        INSERT INTO officers (name, email, password, department)
        VALUES
        ('Sanitation Worker', 'sanitation@test.com', '1234', 'Sanitation Worker'),
        ('Road Inspector', 'road@test.com', '1234', 'Road Inspector'),
        ('Panchayat Officer', 'panchayat@test.com', '1234', 'Panchayat Officer'),
        ('Water Officer', 'water@test.com', '1234', 'Water Officer'),
        ('Electricity Board', 'electricity@test.com', '1234', 'Electricity Board')
        """)
        print("[DB] Seeded test officers into the database.")

    # ======================
    # ADMINS TABLE
    # ======================
    cur.execute("""
    CREATE TABLE IF NOT EXISTS admins (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Default admin (only if not exists)
    cur.execute("SELECT * FROM admins WHERE username='admin'")
    if not cur.fetchone():
        cur.execute(
            "INSERT INTO admins (username, password) VALUES (?, ?)",
            ("admin", "admin123")
        )

    conn.commit()
    conn.close()

# ==============================
# DUPLICATE MASTER
# ==============================

_model = None
def get_model():
    global _model
    if _model is None:
        print("🤖 LOADING AI SIMILARITY MODEL...")
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model

def find_duplicate_master(text):
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("SELECT id, complaint FROM complaints WHERE is_duplicate = 0")
    rows = cur.fetchall()

    if not rows:
        conn.close()
        return None

    model = get_model()
    
    # Batch encode all existing complaints for better performance
    existing_texts = [row["complaint"] for row in rows]
    if not existing_texts:
        conn.close()
        return None
        
    new_embedding = model.encode(text, convert_to_tensor=True)
    existing_embeddings = model.encode(existing_texts, convert_to_tensor=True)
    
    # Calculate cosine similarity for all at once
    cosine_scores = util.cos_sim(new_embedding, existing_embeddings)[0]
    
    for i, score in enumerate(cosine_scores):
        if score.item() > 0.60:  # similarity threshold
            conn.close()
            return rows[i]["id"]

    conn.close()
    return None

def assign_officer(department):
    mapping = {
        "Sanitation": "Sanitation Worker",
        "Roads": "Road Inspector",
        "Water": "Water Officer",
        "Electricity": "Electricity Board",
        "Drainage": "Drainage Officer",
        "General": "Panchayat Officer"
    }
    return mapping.get(department, "Panchayat Officer")

# ==============================
# SAVE COMPLAINT
# ==============================
def save_complaint(text, dept, priority, risk, explanation, user_id, lat=None, lon=None, manual_location=None, image_path=None, address=None, state="Unknown", city="Unknown", area="Unknown", source="user", translated_text=None, mobile=None, location_source="UNKNOWN"):
    print("DEBUG GPS BEFORE SAVE:",lat,lon)
    conn = get_connection()
    cur = conn.cursor()

    master_id = find_duplicate_master(text)
    officer = assign_officer(dept)
    
    # Use translated text for risk if available
    processing_text = translated_text if translated_text else text
    
    # --------------------------
    # RECALCULATE INTELLIGENT RISK
    # --------------------------
    duplicate_count = 0
    if master_id:
        cur.execute("SELECT COUNT(*) FROM complaints WHERE master_id = ? OR id = ?", (master_id, master_id))
        duplicate_count = cur.fetchone()[0]
    
    risk, reasons = ai_agent.calculate_risk(
        processing_text,
        duplicate_count=duplicate_count,
        created_at=datetime.now(),
        department=dept,
        source=source
    )
    
    # Use dynamic reasons instead of whatever was passed
    explanation = str(reasons)
    
    if risk >= 70:
        priority = "HIGH"
    elif risk >= 40:
        priority = "MEDIUM"
    else:
        priority = "LOW"

    if master_id:
        # Save duplicate
        cur.execute("""
            INSERT INTO complaints
            (complaint, department, priority, risk_score, explanation, user_id, master_id, is_duplicate, latitude, longitude, manual_location, image_path, address, state, city, area, source, assigned_officer, translated_text, mobile, location_source)
            VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (text, dept, priority, risk, str(explanation), user_id, master_id, lat, lon, manual_location, image_path, address, state, city, area, source, officer, translated_text, mobile, location_source))
    else:
        # Save master complaint
        cur.execute("""
            INSERT INTO complaints
            (complaint, department, priority, risk_score, explanation, user_id, latitude, longitude, manual_location, image_path, address, state, city, area, source, assigned_officer, translated_text, mobile, location_source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (text, dept, priority, risk, str(explanation), user_id, lat, lon, manual_location, image_path, address, state, city, area, source, officer, translated_text, mobile, location_source))

    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return new_id

def update_complaint_address(complaint_id, address):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE complaints SET address = ?, location_source = 'GPS' WHERE id = ?", (address, complaint_id))
    conn.commit()
    conn.close()

# ==============================
# LOCATION CACHE HELPERS
# ==============================
def get_cached_address(lat, lon):
    if not lat or not lon: return None
    lat_lon = f"{round(float(lat), 5)},{round(float(lon), 5)}"
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT address FROM location_cache WHERE lat_lon = ?", (lat_lon,))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else None

def save_to_cache(lat, lon, address):
    if not lat or not lon or not address: return
    lat_lon = f"{round(float(lat), 5)},{round(float(lon), 5)}"
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("INSERT OR REPLACE INTO location_cache (lat_lon, address) VALUES (?, ?)", (lat_lon, address))
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
def get_all_complaints(state=None, city=None, area=None):
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    query = """
        SELECT 
            id, complaint, department, priority, status,
            risk_score, explanation, created_at,
            latitude, longitude, manual_location, address,
            user_id, source, state, city, area, assigned_officer,
            translated_text, image_path, location_source
        FROM complaints
        WHERE is_duplicate = 0 AND hidden_from_admin = 0
    """

    params = []

    if state:
        query += " AND state = ?"
        params.append(state)
    if city:
        query += " AND city = ?"
        params.append(city)
    if area:
        query += " AND area = ?"
        params.append(area)

    query += " ORDER BY created_at DESC"

    cur.execute(query, tuple(params))
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
        SELECT id, complaint, department, priority, status, risk_score, created_at, image_path, address, state, city, area
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
            "created_at": r[6],
            "image_path": r[7],
            "address": r[8],
            "state": r[9],
            "city": r[10],
            "area": r[11]
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

def get_complaint_by_id(cid):
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("SELECT * FROM complaints WHERE id = ?", (cid,))
    row = cur.fetchone()
    conn.close()

    return dict(row) if row else None

# ==============================
# SMART LOCATION SYNC (BONUS)
# ==============================
def get_active_location():
    """
    Analyzes recent complaints to find the dominant city and coordinates.
    Logic:
    1. Fetch recent complaints (last 50) with locations.
    2. Extract cities from addresses ('address' column).
    3. Find the most frequent city (Clustering).
    4. Return that city's coordinates.
    """
    conn = get_connection()
    cur = conn.cursor()
    
    # Priority: 最近の50件から位置情報のあるものを取得
    cur.execute("""
        SELECT address, latitude, longitude 
        FROM complaints 
        WHERE (address IS NOT NULL AND address != '') 
           OR (latitude IS NOT NULL AND longitude IS NOT NULL)
        ORDER BY created_at DESC 
        LIMIT 50
    """)
    rows = cur.fetchall()
    conn.close()

    default_city = os.getenv("DEFAULT_CITY", "Kolkata")
    # Basic lookup city -> [lat, lon] for centering
    city_defaults = {
        "Kolkata": [22.5726, 88.3639],
        "Bengaluru": [12.9716, 77.5946],
        "Delhi": [28.6139, 77.2090],
        "Mumbai": [19.0760, 72.8777]
    }

    if not rows:
        return {
            "city": default_city,
            "latitude": city_defaults.get(default_city, [22.5726, 88.3639])[0],
            "longitude": city_defaults.get(default_city, [22.5726, 88.3639])[1],
            "source": "environment_default"
        }

    city_counts = {}
    city_to_coords = {}

    for r in rows:
        addr, lat, lon = r[0], r[1], r[2]
        city = None
        
        # Extract city from address
        if addr:
            parts = [p.strip() for p in addr.split(',')]
            # Usually city is near the end but before state/country
            if len(parts) >= 3:
                city = parts[-3] # Example: Bengaluru Urban
            elif len(parts) >= 2:
                city = parts[-2]
            
        if city:
            # Clean up city name
            if "Urban" in city: city = city.replace("Urban", "").strip()
            
            city_counts[city] = city_counts.get(city, 0) + 1
            if lat and lon and city not in city_to_coords:
                city_to_coords[city] = [lat, lon]

    if not city_counts:
        # If no city detected, use latest lat/lon directly
        last = rows[0]
        return {
            "city": default_city,
            "latitude": last[1] or city_defaults[default_city][0],
            "longitude": last[2] or city_defaults[default_city][1],
            "source": "latest_coord_only"
        }

    # Find dominant city
    dominant_city = max(city_counts, key=lambda k: city_counts[k])
    coords = city_to_coords.get(dominant_city)
    
    if not coords:
        coords = city_defaults.get(dominant_city, city_defaults["Kolkata"])

    return {
        "city": dominant_city,
        "latitude": coords[0],
        "longitude": coords[1],
        "source": "dominant_cluster"
    }

def get_officer_workload(state, city, area):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT assigned_officer, COUNT(*) as total
        FROM complaints
        WHERE status != 'RESOLVED'
        AND state = ?
        AND city = ?
        AND area = ?
        GROUP BY assigned_officer
    """, (state, city, area))

    rows = cur.fetchall()
    conn.close()

    result = []
    for r in rows:
        officer = r[0] if r[0] else "Unassigned"
        count = r[1]
        result.append({
            "officer": officer,
            "count": count
        })
    return result

def get_area_alerts(state, city, area):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT area, COUNT(*) as total
        FROM complaints
        WHERE status != 'RESOLVED'
        AND state = ?
        AND city = ?
        AND area = ?
        GROUP BY area
    """, (state, city, area))

    rows = cur.fetchall()
    conn.close()

    alerts = []
    for r in rows:
        area_name = r[0]
        count = r[1]

        if area_name and count >= 3:
            alerts.append({
                "area": area_name,
                "count": count,
                "level": "HIGH"
            })
    return alerts