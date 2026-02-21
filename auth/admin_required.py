from functools import wraps
from flask import request, jsonify, current_app
import jwt

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get("Authorization")

        if not token:
            return jsonify({"error": "Admin token missing"}), 401

        try:
            decoded = jwt.decode(
                token,
                current_app.config["SECRET_KEY"],
                algorithms=["HS256"]
            )

            if decoded.get("role") != "admin":
                return jsonify({"error": "Admin access required"}), 403

        except Exception as e:
            return jsonify({"error": "Invalid admin token"}), 401

        return f(*args, **kwargs)

    return decorated