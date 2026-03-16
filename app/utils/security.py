import secrets
from functools import wraps

from flask import abort, flash, redirect, request, session, url_for

from app.models import fetch_user_by_id


def generate_csrf_token() -> str:
    token = session.get("csrf_token")
    if not token:
        token = secrets.token_hex(16)
        session["csrf_token"] = token
    return token


def validate_csrf() -> bool:
    expected = session.get("csrf_token", "")
    provided = request.form.get("csrf_token", "")
    return bool(expected) and expected == provided


def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if "user_id" not in session:
            flash("Please sign in to continue.", "warning")
            return redirect(url_for("auth.login"))
        return view(*args, **kwargs)

    return wrapped_view


def admin_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        user = current_user()
        if not user or not user["is_admin"]:
            abort(403)
        return view(*args, **kwargs)

    return wrapped_view


def current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    return fetch_user_by_id(user_id)
