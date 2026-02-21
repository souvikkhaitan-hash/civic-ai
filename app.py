from flask import Flask, request, jsonify, render_template
from internet.weather_agent import run_weather_check
from scheduler import start_scheduler
from auth.auth_routes import auth_bp
from auth.auth_middleware import token_required
from database import (
    init_db,
    get_all_complaints,
    enforce_sla,
    get_analytics,
    get_user_complaints,
    save_complaint
)
from ai_agent import analyze_complaint
import os
from dotenv import load_dotenv
import jwt
import datetime
import sqlite3
from admin_auth import admin_required
from internet.weather_agent import weather_intelligence
from internet.intelligence import civic_intelligence
from utils.response import success

app = Flask(__name__, template_folder="templates", static_folder="static")
load_dotenv()
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY")

ADMIN_USERNAME = os.getenv("ADMIN_USERNAME")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")

# Initialize DB
init_db()
app.register_blueprint(auth_bp)

# 🔁 SLA enforcement
@app.before_request
def auto_sla():
    enforce_sla()

# ==========================================
# SUBMIT COMPLAINT
# ==========================================
@app.route("/submit", methods=["POST"])
@token_required
def submit():
    data = request.get_json()
    description = data.get("description")

    ai_result = analyze_complaint(description)

    save_complaint(
        description,
        ai_result.get("department", "General"),
        ai_result.get("priority", "MEDIUM"),
        ai_result.get("risk_score", 0),
        ai_result.get("explanation", []),
        request.user_id
    )

    return jsonify(success(ai_result, "Complaint submitted"))

# ==========================================
# ADMIN LOGIN
# ==========================================
@app.route("/admin-login", methods=["POST"])
def admin_login():
    data = request.get_json()

    if data.get("username") == ADMIN_USERNAME and data.get("password") == ADMIN_PASSWORD:
        token = jwt.encode(
            {"admin": True, "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=12)},
            app.config["SECRET_KEY"],
            algorithm="HS256"
        )
        return jsonify({"token": token})

    return jsonify({"error": "Invalid admin credentials"}), 401

# ==========================================
# ADMIN ROUTES
# ==========================================
@app.route("/admin/complaints")
@admin_required
def admin_complaints():
    complaints = get_all_complaints()
    grouped = {}

    for c in complaints:
        key = c["complaint"].lower().strip()

        if key not in grouped:
            grouped[key] = c.copy()
            grouped[key]["count"] = 1
            grouped[key]["ids"] = [c["id"]] 
            grouped[key]["ids"]=[c["id"]]# 👈 IMPORTANT
        else:
            grouped[key]["count"] += 1
            grouped[key]["ids"].append(c["id"])
            grouped[key]["id"]=min(grouped[key]["ids"])

    return jsonify(list(grouped.values()))

@app.route("/admin-ui")
def admin_ui():
    return render_template("admin.html")

@app.route("/admin-login-ui")
def admin_login_ui():
    return render_template("admin_login.html")

# ==========================================
# UPDATE STATUS
# ==========================================
@app.route("/complaints/<int:complaint_id>/status", methods=["PUT"])
@admin_required
def update_complaint_status(complaint_id):
    data = request.get_json()
    new_status = data.get("status")

    conn = sqlite3.connect("civic_ai.db")
    cur = conn.cursor()

    cur.execute("SELECT status FROM complaints WHERE id=?", (complaint_id,))
    current = cur.fetchone()[0]

    cur.execute("""
        UPDATE complaints
        SET previous_status=?, status=?
        WHERE id=?
    """, (current, new_status, complaint_id))

    conn.commit()
    conn.close()

    return jsonify({"message": "updated"})

# ==========================================
# UNDO STATUS (FIXED)
# ==========================================
@app.route("/complaints/<int:complaint_id>/undo", methods=["PUT"])
@admin_required
def undo_status_route(complaint_id):
    conn = sqlite3.connect("civic_ai.db")
    cur = conn.cursor()

    cur.execute("""
        UPDATE complaints
        SET status = previous_status
        WHERE id=?
    """, (complaint_id,))

    conn.commit()
    conn.close()

    return jsonify({"message": "undone"})

# ==========================================
# DELETE COMPLAINT (FIXED)
# ==========================================
@app.route("/complaints/<int:cid>", methods=["DELETE"])
@admin_required
def delete_complaint(cid):
    conn = sqlite3.connect("civic_ai.db")
    cur = conn.cursor()
    cur.execute("DELETE FROM complaints WHERE id=?", (cid,))
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

if __name__ == "__main__":
    start_scheduler()
    app.run(debug=True)