from functools import wraps
from flask import request, jsonify
import jwt
import os
from dotenv import load_dotenv


load_dotenv()
SECRET_KEY = os.getenv("SECRET_KEY")

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization")

        if not auth_header:
            return jsonify({"error": "Token missing"}), 401

        try:
            token = auth_header.split(" ")[1]
            decoded = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])

            request.user_id = decoded["user_id"]
            request.role = decoded.get("role")

        except Exception as e:
            print("JWT ERROR:", e)  # <-- will show real issue
            return jsonify({"error": "Invalid token"}), 401

        return f(*args, **kwargs)

    return decorated