from flask import Flask, request, jsonify, render_template
from internet.weather_agent import run_weather_check
from scheduler import start_scheduler
import threading
from auth.auth_routes import auth_bp
from auth.auth_middleware import token_required
from database import get_user_complaints
from database import save_complaint
from database import get_user_dashboard
import os
from dotenv import load_dotenv


from database import (
    init_db,
    get_all_complaints,
    update_status,
    undo_status,
    enforce_sla,
    get_analytics
)

from ai_agent import analyze_complaint

app = Flask(__name__)
load_dotenv()
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY")

# Initialize DB
init_db()

app.register_blueprint(auth_bp)


# 🔁 SLA enforcement
@app.before_request
def auto_sla():
    enforce_sla()

# 📩 Submit complaint
@app.route("/submit", methods=["POST"])
@token_required
def submit():
    data = request.get_json()

    if not data or "complaint" not in data:
        return jsonify({"error": "Complaint required"}), 400

    result = analyze_complaint(data["complaint"])
    save_complaint(
        result["complaint"],
        result["department"],
        result["priority"],
        result["risk_score"],
        result["explanation"],
        request.user_id
    )
    result["user_id"] = request.user_id

    return jsonify(result)

# 👤 User complaints
@app.route("/my-complaints", methods=["GET"])
@token_required
def my_complaints():
    try:
        complaints = get_user_complaints(request.user_id)
        return jsonify(complaints)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# 📋 Get all complaints (API)
@app.route("/complaints", methods=["GET"])
def complaints():
    return jsonify(get_all_complaints())

# 🧑‍💼 Admin dashboard
@app.route("/admin")
def admin_dashboard():
    return render_template("admin.html", complaints=get_all_complaints())

# 🔄 Update status
@app.route("/complaints/<int:complaint_id>/status", methods=["PUT"])
def update_complaint_status(complaint_id):
    data = request.get_json()
    status = data.get("status")

    if status not in ["OPEN", "IN_PROGRESS", "RESOLVED"]:
        return jsonify({"error": "Invalid status"}), 400

    update_status(complaint_id, status)
    return jsonify({"message": "Status updated", "new_status": status})

# ↩️ Undo status
@app.route("/complaints/<int:complaint_id>/undo", methods=["PUT"])
def undo_complaint_status(complaint_id):
    undo_status(complaint_id)
    return jsonify({"message": "Status reverted"})

# 🌐 Internet ingestion
@app.route("/internet/weather-check", methods=["POST"])
def weather_check():
    return run_weather_check()

# 📊 Analytics
@app.route("/analytics", methods=["GET"])
def analytics():
    return jsonify(get_analytics())

# ===============================
# USER DASHBOARD (FINAL)
# ===============================
@app.route("/user-dashboard", methods=["GET"])
@token_required
def user_dashboard():
    from database import get_user_complaints

    complaints = get_user_complaints(request.user_id)

    total = len(complaints)

    status_counts = {}
    for c in complaints:
        status = c["status"]
        status_counts[status] = status_counts.get(status, 0) + 1

    return jsonify({
        "total": total,
        "status_counts": status_counts,
        "recent": complaints[:5]
    })

if __name__ == "__main__":
    start_scheduler()
    app.run(debug=True)
