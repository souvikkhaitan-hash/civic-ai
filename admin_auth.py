import jwt
import os
from flask import request, jsonify
from functools import wraps
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

SECRET = os.getenv("SECRET_KEY")


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization")

        # Check token exists
        if not auth_header or not auth_header.startswith("Bearer "):
            return jsonify({"error": "Admin token missing"}), 401

        token = auth_header.split(" ")[1]

        try:
            decoded = jwt.decode(token, SECRET, algorithms=["HS256"])

            # Check role
            if decoded.get("role") != "admin":
                return jsonify({"error": "Access denied (Admin only)"}), 403

        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token expired"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "Invalid admin token"}), 401

        return f(*args, **kwargs)

    return decorated