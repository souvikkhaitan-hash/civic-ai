from flask import Flask, request, jsonify, render_template, session, redirect
import os
import requests
import sqlite3
import threading
import uuid
import sys
from dotenv import load_dotenv
from utils.translator import translate_to_english
from utils.sms import send_sms
from utils.telegram import send_telegram

from database import (
    get_connection,
    init_db,
    get_all_complaints,
    enforce_sla,
    get_analytics,
    get_user_complaints,
    save_complaint,
    get_cached_address,
    get_active_location,
    get_officer_workload,
    get_area_alerts
)

from auth.auth_routes import auth_bp
from auth.auth_middleware import token_required
from admin_auth import admin_required
from ai_agent import analyze_complaint
from internet.weather_agent import run_weather_check, weather_intelligence
from internet.intelligence import civic_intelligence, intelligence_to_complaint
from internet.news_agent import start_news_scheduler
from agents.reddit_agent import start_reddit_scheduler
from scheduler import start_scheduler
from utils.response import success
from utils.geocoder import geocode
from werkzeug.utils import secure_filename

# Configuration
load_dotenv()
app = Flask(__name__, template_folder="templates", static_folder="static")
print("[SYS] Initializing database...")
init_db()
print("TOMTOM KEY LOADED:", os.getenv("TOMTOM_API_KEY"))
def start_background_agents():
    print("[SYS] Starting background agents...")
    threading.Thread(target=start_scheduler, daemon=True).start()
    threading.Thread(target=start_reddit_scheduler, daemon=True).start()
    threading.Thread(target=start_news_scheduler, daemon=True).start()

# start them immediately
# Configuration
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret-key")
app.config['UPLOAD_FOLDER'] = os.path.join('static', 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # 5MB
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}


# Ensure folders
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Initialize DB and Register Blueprints
app.register_blueprint(auth_bp)

# 🔁 SLA enforcement (Moved to background scheduler to avoid DB locking)

def geocode_complaint_task(complaint_id, lat, lon):
    """Background task to geocode and update address"""
    try:
        if not lat or not lon: return
        
        # Check cache first
        address = get_cached_address(lat, lon)
        if not address:
            address = geocode(lat, lon)
            if address:
                save_to_cache(lat, lon, address)
        
        if address:
            update_complaint_address(complaint_id, address)
            print(f"[GEO] Geocoded ID {complaint_id}: {address}")
    except Exception as e:
        print(f"Geocode task error for ID {complaint_id}: {e}")

def is_valid_coord(val):
    try:
        return val not in [None, "", "undefined", "null"] and float(val) != 0
    except:
        return False

# ==========================================
# SUBMIT COMPLAINT
# ==========================================
@app.route("/submit", methods=["POST"])
@app.route("/submit-complaint", methods=["POST"])
@token_required
def submit():
    image_path = None
    
    # --------------------------
    # FLEXIBLE DATA PARSER
    # --------------------------
    if request.is_json:
        data = request.get_json()
        description = data.get("complaint") or data.get("description")
        lat = data.get("latitude")
        lon = data.get("longitude")
        manual_location = data.get("location_text") or data.get("location")
        state = data.get("state") or session.get("state") or "Karnataka"
        city = data.get("city") or session.get("city") or "Bengaluru"
        area = data.get("area") or session.get("area") or "Rajanukunte"
        mobile = data.get("mobile") or "Unknown"
    else:
        description = request.form.get("complaint") or request.form.get("description")
        lat = request.form.get("latitude")
        lon = request.form.get("longitude")
        manual_location = request.form.get("location_text") or request.form.get("location")
        state = request.form.get("state") or session.get("state") or "Karnataka"
        city = request.form.get("city") or session.get("city") or "Bengaluru"
        area = request.form.get("area") or session.get("area") or "Rajanukunte"
        mobile = request.form.get("mobile") or "Unknown"
        
        if 'image' in request.files:
            file = request.files['image']
            if file and file.filename != '' and allowed_file(file.filename):
                filename = secure_filename(str(uuid.uuid4()) + "_" + file.filename)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                image_path = f"uploads/{filename}"

    if not description:
        return jsonify({"success": False, "error": "Missing description"}), 400

    print("DEBUG INPUT:", lat, lon, type(lat), type(lon))

    # --------------------------
    # MULTI-LANGUAGE SUPPORT
    # --------------------------
    translated_text = translate_to_english(description)

    # --------------------------
    # AI ANALYSIS
    # --------------------------
    ai_result = analyze_complaint(translated_text or description, lat, lon)

    # --------------------------
    # FINAL LOCATION LOGIC (FIXED)
    # --------------------------
    has_gps = is_valid_coord(lat) and is_valid_coord(lon)

    if has_gps:
        location_source = "GPS"
        lat = float(lat)
        lon = float(lon)
        address_final = f"{area}, {city}, {state}"

    elif area and area != "Unknown":
        location_source = "USER_SELECTED"
        lat = None
        lon = None
        address_final = f"{area}, {city}, {state}"

    else:
        location_source = "AI_ESTIMATED"
        lat = None
        lon = None
        address_final = f"{city} (AI Estimated)"

    print(f"[LOCATION FINAL] {location_source} | {address_final} | {lat},{lon}")

    # --------------------------
    # SAVE COMPLAINT (FIXED)
    # --------------------------
    complaint_id = save_complaint(
        text=description,
        dept=ai_result["department"],
        priority=ai_result["priority"],
        risk=ai_result["risk_score"],
        explanation=ai_result["explanation"],
        user_id=request.user_id,
        lat=lat,                     # ✅ FIXED (no condition)
        lon=lon,                     # ✅ FIXED
        manual_location=manual_location,
        image_path=image_path,
        address=address_final,
        state=state,
        city=city,
        area=area,
        source="user",
        translated_text=translated_text,
        mobile=mobile,
        location_source=location_source
    )

    # --------------------------
    # NOTIFICATIONS
    # --------------------------
    if mobile and mobile != "Unknown":
        try:
            send_sms(mobile, f"Complaint Registered! ID: #{complaint_id}")
        except:
            pass

    send_telegram(f"🚨 Complaint #{complaint_id} in {area} ({city})")

    # --------------------------
    # BACKGROUND GEOCODE
    # --------------------------
    if lat and lon:
        threading.Thread(
            target=geocode_complaint_task,
            args=(complaint_id, lat, lon),
            daemon=True
        ).start()

    return jsonify(success(ai_result, "Complaint submitted"))
# ===============================
# ADMIN REGION SELECTION
# ===============================

@app.route("/admin/select-location")
def admin_select_location():
    if not session.get("admin"):
        return redirect("/admin-login-ui")
    return render_template("select_location.html")

@app.route("/admin/set-location", methods=["POST"])
def admin_set_location():
    if not session.get("admin"):
        return jsonify({"error": "Unauthorized"}), 401
    
    data = request.get_json() or request.form
    session["state"] = data.get("state")
    session["city"] = data.get("city")
    session["area"] = data.get("area")
    
    return jsonify({"success": True, "redirect": "/admin-ui"})

# ==========================================
# ADMIN ROUTES
# ==========================================
@app.route("/admin/complaints")
@admin_required
def admin_complaints():
    state = session.get("state")
    city = session.get("city")
    area = session.get("area")
    
    complaints = get_all_complaints(state=state, city=city, area=area)
    
    # Transformation: Add proof_url for image rendering
    for c in complaints:
        if c.get("image_path"):
            c["proof_url"] = f"/static/{c['image_path']}"
        else:
            c["proof_url"] = None

    return jsonify(complaints)

@app.route("/admin/officer-workload")
def officer_workload():
    state = session.get("state")
    city = session.get("city")
    area = session.get("area")
    data = get_officer_workload(state, city, area)
    return jsonify(data)

@app.route("/admin/area-alerts")
def area_alerts():
    state = session.get("state")
    city = session.get("city")
    area = session.get("area")
    alerts = get_area_alerts(state, city, area)
    return jsonify(alerts)

@app.route("/assign-officer", methods=["POST"])
@admin_required
def assign_officer():
    data = request.get_json()
    complaint_id = data.get("complaint_id")
    officer = data.get("officer")

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        UPDATE complaints
        SET assigned_officer = ?
        WHERE id = ?
    """, (officer, complaint_id))

    conn.commit()
    conn.close()

    return jsonify({"success": True})

@app.route("/send-to-officer", methods=["POST"])
@admin_required
def send_to_officer():
    data = request.get_json()
    complaint_id = data.get("complaint_id")

    conn = get_connection()
    cur = conn.cursor()

    # Get assigned officer
    cur.execute("SELECT assigned_officer FROM complaints WHERE id=?", (complaint_id,))
    row = cur.fetchone()

    if not row or not row[0]:
        return jsonify({"error": "No officer assigned"}), 400

    officer = row[0]

    # Update status
    cur.execute("""
        UPDATE complaints
        SET status = 'ASSIGNED'
        WHERE id = ?
    """, (complaint_id,))

    conn.commit()
    conn.close()

    # Telegram notification
    from utils.telegram import send_telegram
    send_telegram(f"📨 Complaint #{complaint_id} assigned to {officer}")

    return jsonify({"success": True})

# ==========================================
# OFFICER LOGIN & DASHBOARD
# ==========================================

@app.route("/officer-login", methods=["GET", "POST"])
def officer_login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        conn = get_connection()
        cur = conn.cursor()

        cur.execute("""
            SELECT id, department FROM officers
            WHERE email=? AND password=?
        """, (email, password))

        officer = cur.fetchone()
        conn.close()

        if officer:
            session["officer_id"] = officer[0]
            session["officer_department"] = officer[1]
            return redirect("/officer-dashboard")

        return render_template("officer_login.html", error="Invalid credentials")

    return render_template("officer_login.html")

@app.route("/officer-dashboard")
def officer_dashboard():
    if "officer_id" not in session:
        return redirect("/officer-login")

    department = session.get("officer_department")

    conn = get_connection()
    cur = conn.cursor()

    # Get complaints for this officer (only those already assigned)
    cur.execute("""
        SELECT * FROM complaints
        WHERE assigned_officer = ? AND status != 'OPEN' AND hidden_from_officer = 0
        ORDER BY created_at DESC
    """, (department,))

    complaints_raw = cur.fetchall()
    conn.close()

    # Transform: Add proof_url for template image rendering
    complaints = []
    for c in complaints_raw:
        item = dict(c)
        if item.get("image_path"):
            item["proof_url"] = f"/static/{item['image_path']}"
        else:
            item["proof_url"] = None
        complaints.append(item)

    return render_template("officer_dashboard.html", complaints=complaints)

@app.route("/admin/map-center")
def map_center():
    state = session.get("state")
    city = str(session.get("city") or "").strip()
    area = session.get("area")
    
    print(f"[MAP CENTER] Request for City: '{city}', Session: {session}")

    if not city:
        return jsonify({
            "latitude": 22.5726,
            "longitude": 88.3639,
            "source": "fallback"
        })
        
    location_map = {
        "kolkata": [22.5726, 88.3639],
        "bengaluru": [12.9716, 77.5946],
        "bangalore": [12.9716, 77.5946],
        "delhi": [28.6139, 77.2090],
        "mumbai": [19.0760, 72.8777]
    }
    
    coords = location_map.get(city.lower(), [12.9716, 77.5946])
    
    return jsonify({
        "latitude": coords[0],
        "longitude": coords[1],
        "source": "admin_area"
    })


@app.route("/admin-ui")
@admin_required
def admin_ui():
    state = session.get("state")
    city = session.get("city")
    area = session.get("area") or "Rajanukunte"

    AREA_COORDS = {
        "Rajanukunte": [13.1734, 77.5636],
        "Yelahanka": [13.1007, 77.5963],
        "Whitefield": [12.9698, 77.7500]
    }

    center = AREA_COORDS.get(area, [12.9716, 77.5946])

    return render_template("admin.html", 
        center=center,
        region={"state": state, "city": city, "area": area}
    )

@app.route("/admin-login", methods=["GET"])
def admin_login_ui_route():
    return render_template("admin_login.html")

@app.route("/admin-logout")
def admin_logout():
    session.pop("admin", None)
    return redirect("/admin-login")

@app.route("/complaints/<int:complaint_id>/status", methods=["PUT"])
@admin_required
def update_complaint_status(complaint_id):
    data = request.get_json()
    new_status = data.get("status")

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT user_id, status FROM complaints WHERE id=?", (complaint_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return jsonify({"error": "Not found"}), 404
    
    owner_id, current_status = row

    cur.execute("""
        UPDATE complaints
        SET previous_status=?, status=?
        WHERE id=? OR master_id=?
    """, (current_status, new_status, complaint_id, complaint_id))
    
    
    # --------------------------
    # REAL-TIME NOTIFICATION (ADMIN)
    # --------------------------
    msg = f"Status Update: Complaint #{complaint_id} set to {new_status}"
    if new_status == "RESOLVED": msg = f"✅ Complaint #{complaint_id} has been RESOLVED"
    elif new_status == "IN_PROGRESS": msg = f"🚧 Complaint #{complaint_id} is now IN PROGRESS"
    elif new_status == "ASSIGNED": msg = f"👤 Complaint #{complaint_id} has been ASSIGNED to Officer"

    cur.execute("INSERT INTO notifications (message, type) VALUES (?, ?)", (msg, new_status))
    
    # 🔥 TELEGRAM
    cur.execute("SELECT area FROM complaints WHERE id=?", (complaint_id,))
    row = cur.fetchone()
    tel_msg = f"{msg}\n📍 {row['area'] or 'Unknown'}"
    send_telegram(tel_msg)

    conn.commit()
    conn.close()

    return jsonify({"message": "updated", "success": True})

@app.route("/update_status", methods=["POST"])
def update_status_route_new():
    data = request.get_json()
    complaint_id = data.get("id")
    status = data.get("status")

    if not complaint_id or not status:
        return jsonify({"error": "Missing id/status"}), 400

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("UPDATE complaints SET status = ? WHERE id = ?", (status, complaint_id))
    
    # NOTIFICATION
    msg = f"Officer Update: Complaint #{complaint_id} -> {status}"
    if status == "IN_PROGRESS": msg = f"🚧 Field work started on Complaint #{complaint_id}"
    elif status == "RESOLVED": msg = f"✅ Field work COMPLETED on Complaint #{complaint_id}"

    cur.execute("INSERT INTO notifications (message, type) VALUES (?, ?)", (msg, status))
    send_telegram(msg)

    conn.commit()
    conn.close()

    return jsonify({"success": True})

# ==========================================
# EXPLICIT UNDO & DELETE ROUTES (REQUESTED)
# ==========================================
@app.route("/delete-complaint", methods=["POST"])
#@admin_required # Keeping consistent with request though normally admin required
def delete_complaint_explicit():
    data = request.get_json()
    complaint_id = data.get("complaint_id")

    conn = get_connection()
    cur = conn.cursor()

    if session.get("admin"):
        cur.execute("UPDATE complaints SET hidden_from_admin = 1 WHERE id=?", (complaint_id,))
    elif session.get("officer_id"):
        cur.execute("UPDATE complaints SET hidden_from_officer = 1 WHERE id=?", (complaint_id,))
    else:
        # Fallback to physical delete if no role session found
        cur.execute("DELETE FROM complaints WHERE id=?", (complaint_id,))

    conn.commit()
    conn.close()

    return jsonify({"success": True})

@app.route("/undo-status", methods=["POST"])
def undo_status_explicit():
    data = request.get_json()
    complaint_id = data.get("complaint_id")

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT status FROM complaints WHERE id=?", (complaint_id,))
    row = cur.fetchone()
    if not row:
        return jsonify({"error": "not found"})
    status = row[0]

    new_status = status

    if status == "IN_PROGRESS":
        new_status = "ASSIGNED"
    elif status == "RESOLVED":
        new_status = "IN_PROGRESS"

    cur.execute("""
        UPDATE complaints SET status=?
        WHERE id=?
    """, (new_status, complaint_id))

    conn.commit()
    conn.close()

    return jsonify({"success": True})

# ==========================================
# UNDO STATUS (FIXED)
# ==========================================
@app.route("/complaints/<int:complaint_id>/undo", methods=["PUT"])
@admin_required
def undo_status_route(complaint_id):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
    UPDATE complaints
    SET status = previous_status
    WHERE id=? OR master_id=?
""", (complaint_id, complaint_id))

    conn.commit()
    conn.close()

    return jsonify({"message": "undone"})

# ==========================================
# DELETE COMPLAINT (FIXED)
# ==========================================
@app.route("/complaints/<int:cid>", methods=["DELETE"])
@admin_required
def delete_complaint(cid):
    conn = get_connection()
    cur = conn.cursor()

    # find master
    cur.execute("SELECT master_id FROM complaints WHERE id=?", (cid,))
    row = cur.fetchone()

    root_id = row[0] if row and row[0] else cid

    cur.execute("""
        DELETE FROM complaints
        WHERE id=? OR master_id=?
    """, (root_id, root_id))

    conn.commit()
    conn.close()

    return jsonify({"message": "Deleted"})
# ==========================================
# OTHER ROUTES
# ==========================================
@app.route("/internet/weather-check", methods=["POST"])
def weather_check():
    return run_weather_check()

@app.route("/analytics", methods=["GET"])
def analytics():
    return jsonify(get_analytics())

@app.route("/intel/weather")
def weather_intel_api():
    return weather_intelligence()

@app.route("/intel/civic")
def get_civic_intel():
    lat = request.args.get("lat")
    lon = request.args.get("lon")

    if not lat or not lon:
        return {"error": "Missing lat/lon"}

    return civic_intelligence(lat, lon)

@app.errorhandler(Exception)
def global_error(e):
    import traceback
    with open("error.log", "a") as f:
        f.write("\n" + "="*50 + "\n")
        f.write(f"ERR: {str(e)}\n")
        f.write(traceback.format_exc())
    print("ERROR:", e)
    return jsonify({
        "success": False,
        "error": str(e)
    }), 500


@app.route("/ai/intelligence", methods=["POST"])
def intelligence_api():
    data = request.get_json()
    lat = data.get("latitude")
    lon = data.get("longitude")

    return jsonify(intelligence_to_complaint(lat, lon))

@app.route("/ai-map")
def ai_map():
    if not session.get("admin"):
        return redirect("/admin-login-ui")

    region = {"state": session.get("state"), "city": session.get("city"), "area": session.get("area")}
    
    # Define area → coordinates mapping
    AREA_COORDS = {
        "rajanukunte": [13.1736, 77.6370],
        "yelahanka": [13.1007, 77.5963],
        "whitefield": [12.9698, 77.7500],
    }

    # Get selected area safely
    selected_area = ""
    if region and "area" in region and region["area"]:
        selected_area = region["area"].lower().strip()

    # Get center coordinates
    center = AREA_COORDS.get(selected_area, [12.9716, 77.5946])  # fallback Bangalore

    # Debug logs
    print("REGION:", region)
    print("SELECTED AREA:", selected_area)
    print("CENTER:", center)

    return render_template(
        "map.html",
        region=region,
        center=center
    )

# ===============================
# WEATHER API FOR DASHBOARD
# ===============================
@app.route("/api/weather")
def api_weather():
    try:
        city = request.args.get("city")
        data = weather_intelligence(city_name=city)
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/admin/active-location")
@admin_required
def active_location_api():
    try:
        return jsonify(get_active_location())
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    

# ===============================
# USER PAGES (TEMPLATES)
# ===============================

@app.route("/")
def login_type():
    return render_template("logintype.html")


@app.route("/user-login-ui")
def user_login_ui():
    return render_template("userlogin.html")


@app.route("/register-ui")
def register_ui():
    return render_template("newuser.html")


@app.route("/user-dashboard")
def user_dashboard_ui():
    return render_template("user-dashboard.html")

@app.route("/user/complaints")
@token_required
def user_complaints():
    return jsonify(get_user_complaints(request.user_id))
    
@app.route('/favicon.ico')
def favicon():
    return "", 204

@app.route("/api/traffic")
def traffic_api():
    lat = request.args.get("lat")
    lon = request.args.get("lon")

    if not lat or not lon:
        return {"error": "Missing coordinates"}, 400

    api_key = os.getenv("TOMTOM_API_KEY")

    # 🔴 DEBUG
    print("📍 TRAFFIC REQUEST:", lat, lon)
    print("🔑 API KEY:", api_key)

    # ❌ If API key missing → return fallback
    if not api_key:
        print("❌ NO API KEY - USING MOCK DATA")
        return {
            "speed": 25,
            "free_speed": 50,
            "congestion": "MEDIUM",
            "coordinates": [
                [float(lat), float(lon)],
                [float(lat)+0.001, float(lon)+0.001]
            ]
        }

    url = f"https://api.tomtom.com/traffic/services/4/flowSegmentData/absolute/10/json?point={lat},{lon}&key={api_key}"

    try:
        res = requests.get(url, timeout=5)

        print("🌐 STATUS:", res.status_code)

        if res.status_code != 200:
            print("❌ API FAILED:", res.text)
            raise Exception("Traffic API failed")

        data = res.json()

        flow = data.get("flowSegmentData", {})

        coords = []
        if "coordinates" in flow and "coordinate" in flow["coordinates"]:
            raw_coords = flow["coordinates"]["coordinate"]
            coords = [[c["latitude"], c["longitude"]] for c in raw_coords]

        speed = flow.get("currentSpeed", 0)
        free_speed = flow.get("freeFlowSpeed", 1)

        # 🚦 Traffic logic
        if speed < (free_speed * 0.5):
            congestion = "HIGH"
        elif speed < (free_speed * 0.75):
            congestion = "MEDIUM"
        else:
            congestion = "LOW"

        return {
            "speed": speed,
            "free_speed": free_speed,
            "congestion": congestion,
            "coordinates": coords
        }

    except Exception as e:
        print("❌ TRAFFIC ERROR:", e)

        # ✅ FALLBACK (VERY IMPORTANT)
        return {
            "speed": 20,
            "free_speed": 40,
            "congestion": "HIGH",
            "coordinates": [
                [float(lat), float(lon)],
                [float(lat)+0.001, float(lon)+0.001]
            ]
        }


# =====================================
# USER DELETE OWN COMPLAINT
# =====================================
@app.route("/user/delete/<int:cid>", methods=["DELETE"])
@token_required
def user_delete(cid):
    user_id = request.user_id

    conn = get_connection()
    cur = conn.cursor()

    # 1️⃣ Get complaint info
    cur.execute("SELECT user_id, master_id FROM complaints WHERE id=?", (cid,))
    row = cur.fetchone()

    if not row:
        return jsonify({"error": "Not found"}), 404

    owner, master_id = row

    # ownership check
    if owner != user_id:
        return jsonify({"error": "Not allowed"}), 403

    # 2️⃣ find real master id
    root_id = master_id if master_id else cid

    # 3️⃣ delete FULL GROUP
    cur.execute("""
        DELETE FROM complaints
        WHERE id=? OR master_id=?
    """, (root_id, root_id))

    conn.commit()
    conn.close()

    return jsonify({"success": True})

# ==========================================
# NOTIFICATION SYSTEM API
# ==========================================
@app.route("/notifications")
def get_notifications():
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM notifications ORDER BY created_at DESC LIMIT 10")
    rows = cur.fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.route("/notifications/read", methods=["POST"])
def mark_notifications_read():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE notifications SET is_read = 1")
    conn.commit()
    conn.close()
    return jsonify({"success": True})

if __name__ == "__main__":
    from database import init_db
    init_db()
    start_background_agents()
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)