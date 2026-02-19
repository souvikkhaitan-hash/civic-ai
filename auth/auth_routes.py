from flask import Blueprint, request, jsonify
from database import get_connection
from auth.auth_utils import hash_password, verify_password, create_token

# ✅ THIS LINE IS THE FIX
auth_bp = Blueprint("auth", __name__)

# ==========================
# USER REGISTER
# ==========================
@auth_bp.route("/auth/register", methods=["POST"])
def register_user():
    data = request.json
    name = data.get("name")
    email = data.get("email")
    password = data.get("password")

    if not all([name, email, password]):
        return jsonify({"error": "Missing fields"}), 400

    conn = get_connection()
    cur = conn.cursor()

    try:
        cur.execute("""
            INSERT INTO users (name, email, password)
            VALUES (?, ?, ?)
        """, (name, email, hash_password(password)))
        conn.commit()
    except:
        return jsonify({"error": "User already exists"}), 400
    finally:
        conn.close()

    return jsonify({"message": "User registered successfully"})


# ==========================
# USER LOGIN
# ==========================
@auth_bp.route("/auth/login", methods=["POST"])
def login_user():
    data = request.json
    email = data.get("email")
    password = data.get("password")

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, password FROM users WHERE email=?", (email,))
    row = cur.fetchone()
    conn.close()

    if not row:
        return jsonify({"error": "User not found"}), 404

    user_id, hashed = row

    if not verify_password(password, hashed):
        return jsonify({"error": "Invalid password"}), 401

    token = create_token(user_id, "user")
    return jsonify({"token": token})


# ==========================
# OFFICER LOGIN
# ==========================
@auth_bp.route("/auth/officer-login", methods=["POST"])
def officer_login():
    data = request.json
    email = data.get("email")
    password = data.get("password")

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, password FROM officers WHERE email=?", (email,))
    row = cur.fetchone()
    conn.close()

    if not row:
        return jsonify({"error": "Officer not found"}), 404

    officer_id, hashed = row

    try:
        if not verify_password(password,hashed):
            return jsonify({"error":"Invalid password"}),401
    except:
        if password!=hashed:
            return jsonify({"error":"Invalid password"}),401

    token = create_token(officer_id, "officer")
    return jsonify({"token": token})