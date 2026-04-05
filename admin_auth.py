from functools import wraps
from flask import session, jsonify, redirect

def admin_required(f):
    def wrapper(*args, **kwargs):
        if "admin" not in session:
            return redirect("/admin-login")
        return f(*args, **kwargs)
    wrapper.__name__ = f.__name__
    return wrapper