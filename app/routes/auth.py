from datetime import datetime
import secrets

from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from app.database import BLIND_SQLI_FLAG, get_connection
from app.utils.security import generate_csrf_token, validate_csrf


auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        if not validate_csrf():
            flash("Invalid CSRF token.", "danger")
            return redirect(url_for("auth.register"))

        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "").strip()
        bio = request.form.get("bio", "").strip()

        if not username or not email or not password:
            flash("All required fields must be filled in.", "danger")
            return redirect(url_for("auth.register"))

        with get_connection() as connection:
            try:
                connection.execute(
                    """
                    INSERT INTO users (username, email, password, bio, avatar, is_admin, email_verified)
                    VALUES (?, ?, ?, ?, ?, 0, 0)
                    """,
                    (username, email, password, bio, "/static/uploads/default-avatar.png"),
                )
                connection.commit()
            except Exception:
                flash("That username or email already exists.", "danger")
                return redirect(url_for("auth.register"))

        flash("Account created. Please sign in.", "success")
        return redirect(url_for("auth.login"))

    return render_template("register.html", csrf_token=generate_csrf_token())


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if not validate_csrf():
            flash("Invalid CSRF token.", "danger")
            return redirect(url_for("auth.login"))

        identity = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        with get_connection() as connection:
            user = connection.execute(
                "SELECT * FROM users WHERE username = ? OR email = ?",
                (identity, identity),
            ).fetchone()

        bootstrap_admin_login = (
            user
            and user["username"] == "admin"
            and user["password"] == BLIND_SQLI_FLAG
            and password == "admin123"
        )
        if not user or (user["password"] != password and not bootstrap_admin_login):
            flash("Invalid credentials.", "danger")
            return redirect(url_for("auth.login"))

        session["user_id"] = user["id"]
        generate_csrf_token()
        flash(f"Welcome back, {user['username']}.", "success")
        return redirect(url_for("posts.index"))

    return render_template("login.html", csrf_token=generate_csrf_token())


@auth_bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    reset_requested = False
    if request.method == "POST":
        if not validate_csrf():
            flash("Invalid CSRF token.", "danger")
            return redirect(url_for("auth.forgot_password"))

        email = request.form.get("email", "").strip()
        with get_connection() as connection:
            user = connection.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
            if user:
                token = secrets.token_urlsafe(24)
                now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
                connection.execute(
                    """
                    INSERT INTO password_resets (user_id, token, created_at, used)
                    VALUES (?, ?, ?, 0)
                    """,
                    (user["id"], token, now),
                )
                reset_link = url_for("auth.reset_password", token=token, _external=True)
                connection.execute(
                    """
                    INSERT INTO mail_messages (recipient_email, subject, body, created_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        email,
                        "Password reset request",
                        f"Use this recovery link to reset your password: {reset_link}",
                        now,
                    ),
                )
                connection.commit()

        reset_requested = True
        flash("If that address exists, recovery instructions have been sent.", "info")

    return render_template(
        "forgot_password.html",
        csrf_token=generate_csrf_token(),
        reset_requested=reset_requested,
    )


@auth_bp.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token: str):
    with get_connection() as connection:
        reset_record = connection.execute(
            """
            SELECT password_resets.*, users.username
            FROM password_resets
            JOIN users ON users.id = password_resets.user_id
            WHERE token = ? AND used = 0
            ORDER BY password_resets.id DESC
            """,
            (token,),
        ).fetchone()

    if not reset_record:
        flash("That reset link is invalid or has already been used.", "danger")
        return redirect(url_for("auth.login"))

    if request.method == "POST":
        if not validate_csrf():
            flash("Invalid CSRF token.", "danger")
            return redirect(url_for("auth.reset_password", token=token))

        new_password = request.form.get("password", "").strip()
        if not new_password:
            flash("A new password is required.", "danger")
            return redirect(url_for("auth.reset_password", token=token))

        with get_connection() as connection:
            connection.execute(
                "UPDATE users SET password = ? WHERE id = ?",
                (new_password, reset_record["user_id"]),
            )
            connection.execute(
                "UPDATE password_resets SET used = 1 WHERE id = ?",
                (reset_record["id"],),
            )
            connection.commit()

        flash("Password updated. You can sign in now.", "success")
        return redirect(url_for("auth.login"))

    return render_template(
        "reset_password.html",
        csrf_token=generate_csrf_token(),
        reset_record=reset_record,
    )


@auth_bp.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("posts.index"))
