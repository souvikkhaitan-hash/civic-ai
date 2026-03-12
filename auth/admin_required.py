from functools import wraps
from flask import session, jsonify

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        # ✅ Use Flask session instead of JWT
        if not session.get("admin"):
            return jsonify({"error": "Admin login required"}), 401

        return f(*args, **kwargs)

    return decorated