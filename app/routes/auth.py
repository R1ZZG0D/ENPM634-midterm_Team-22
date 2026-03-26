from datetime import datetime
import secrets

from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from app.database import get_connection
from app.utils.security import generate_csrf_token, validate_csrf


auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/register", methods=["GET", "POST"])
# registering a new user
def register():
    if request.method == "POST":
        if not validate_csrf():
            flash("Invalid CSRF token.", "danger")
            return redirect(url_for("auth.register"))

        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "").strip()
        bio = request.form.get("bio", "").strip()

        # make sure all fields are filled in
        if not username or not email or not password:
            flash("All required fields must be filled in.", "danger")
            return redirect(url_for("auth.register"))

        # add the new user into the database
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
            
            # handle collisions with existing users
            except Exception:
                flash("That username or email already exists.", "danger")
                return redirect(url_for("auth.register"))

        flash("Account created. Please sign in.", "success")
        return redirect(url_for("auth.login"))

    return render_template("register.html", csrf_token=generate_csrf_token())


@auth_bp.route("/login", methods=["GET", "POST"])
# logging in
def login():
    if request.method == "POST":
        if not validate_csrf():
            flash("Invalid CSRF token.", "danger")
            return redirect(url_for("auth.login"))

        identity = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        # check if username or email is in database
        with get_connection() as connection:
            user = connection.execute(
                "SELECT * FROM users WHERE username = ? OR email = ?",
                (identity, identity),
            ).fetchone()

        # if user doesn't exist or if password doesn't match, return Invalid credentials
        if not user or user["password"] != password:
            flash("Invalid credentials.", "danger")
            return redirect(url_for("auth.login"))

        # login success
        session["user_id"] = user["id"]
        # set up a csrf token for this session
        generate_csrf_token()
        flash(f"Welcome back, {user['username']}.", "success")
        return redirect(url_for("posts.index"))

    return render_template("login.html", csrf_token=generate_csrf_token())


@auth_bp.route("/forgot-password", methods=["GET", "POST"])
# forgot password feature
def forgot_password():
    reset_requested = False
    if request.method == "POST":
        if not validate_csrf():
            flash("Invalid CSRF token.", "danger")
            return redirect(url_for("auth.forgot_password"))

        email = request.form.get("email", "").strip()
        with get_connection() as connection:
            
            # find user with a matching email
            user = connection.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
            
            # if user found, add the info to password_resets db 
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

                # generate reset password link using random token
                reset_link = url_for("auth.reset_password", token=token, _external=True)

                # update mail_messages db with the pw reset link email
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
# visiting password reset link
def reset_password(token: str):
    with get_connection() as connection:

        # get the reset record from the password_resets db
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

    # if the reset record is not found, show message
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

        # update the users db with the new password
        with get_connection() as connection:
            connection.execute(
                "UPDATE users SET password = ? WHERE id = ?",
                (new_password, reset_record["user_id"]),
            )

            # update that this password reset link has been used
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
