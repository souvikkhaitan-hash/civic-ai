from flask import Flask, request, jsonify, render_template, session, redirect
import os
import sqlite3
import threading
import uuid
import sys
from dotenv import load_dotenv

from database import (
    get_connection,
    init_db,
    get_all_complaints,
    enforce_sla,
    get_analytics,
    get_user_complaints,
    save_complaint,
    get_cached_address,
    save_to_cache,
    update_complaint_address,
    get_active_location
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

# ==========================================
# SUBMIT COMPLAINT
# ==========================================
@app.route("/submit", methods=["POST"])
@token_required
def submit():
    image_path = None
    
    if request.is_json:
        data = request.get_json()
        description = data.get("description")
        lat = data.get("latitude")
        lon = data.get("longitude")
        manual_location = data.get("location_text")
    else:
        # Handle multipart/form-data
        description = request.form.get("description")
        lat = request.form.get("latitude")
        lon = request.form.get("longitude")
        manual_location = request.form.get("location_text")
        
        if 'image' in request.files:
            file = request.files['image']
            if file and file.filename != '' and allowed_file(file.filename):
                filename = secure_filename(str(uuid.uuid4()) + "_" + file.filename)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                image_path = f"uploads/{filename}"

    if not description:
        return jsonify({"success": False, "error": "Missing description"}), 400

    ai_result = analyze_complaint(description, lat, lon)
    print("AI RESULT:", ai_result)  # <-- DEBUGGING LINE

    # SAVE complaint
    complaint_id = save_complaint(
        description,
        ai_result.get("department", "General"),
        ai_result.get("priority", "LOW"),
        ai_result.get("risk_score", 10),
        ai_result.get("explanation", []),
        request.user_id,
        lat,
        lon,
        manual_location,
        image_path
    )

    # Trigger background geocoding (non-blocking)
    if lat and lon:
        threading.Thread(
            target=geocode_complaint_task,
            args=(complaint_id, lat, lon),
            daemon=True
        ).start()

    return jsonify(success(ai_result, "Complaint submitted"))
# ==========================================
# ADMIN LOGIN
# ==========================================


# ==========================================
# ADMIN ROUTES
# ==========================================
@app.route("/admin/complaints")
@admin_required
def admin_complaints():
    complaints = get_all_complaints()
    return jsonify(complaints)

@app.route("/admin-ui")
def admin_ui():
    if not session.get("admin"):
        return redirect("/admin-login-ui")
    return render_template("admin.html")

@app.route("/admin-login-ui")
def admin_login_ui():
    return render_template("admin_login.html")

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
    
    
    conn.commit()
    conn.close()

    return jsonify({"message": "updated"})

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
    return render_template("map.html")

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

if __name__ == "__main__":
    print("Initializing database and starting server...")
    init_db()
    
    # 🔁 Prevent schedulers from starting twice in Flask Debug Mode
    if not app.debug or os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        print("[SYS] Starting background agents...")
        start_scheduler()
        start_reddit_scheduler()
        start_news_scheduler()
    
    app.run(debug=True, use_reloader=True)