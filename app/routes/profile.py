from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from app.database import UPLOAD_DIR, get_connection
from app.models import fetch_user_by_username
from app.utils.security import current_user, generate_csrf_token, login_required, validate_csrf


profile_bp = Blueprint("profile", __name__)


@profile_bp.route("/profile/<username>")
def view_profile(username: str):
    user = fetch_user_by_username(username)
    if not user:
        flash("User not found.", "warning")
        return redirect(url_for("posts.index"))

    with get_connection() as connection:
        posts = connection.execute(
            "SELECT * FROM posts WHERE author_id = ? ORDER BY created_at DESC",
            (user["id"],),
        ).fetchall()

    return render_template("profile.html", profile_user=user, posts=posts)


@profile_bp.route("/profile/edit", methods=["GET", "POST"])
@login_required
def edit_profile():
    user = current_user()
    if request.method == "POST":
        if not validate_csrf():
            flash("Invalid CSRF token.", "danger")
            return redirect(url_for("profile.edit_profile"))

        bio = request.form.get("bio", "")
        avatar_file = request.files.get("avatar")
        avatar_path = user["avatar"]

        if avatar_file and avatar_file.filename:
            filename = f"{user['username']}_{avatar_file.filename}"
            save_path = UPLOAD_DIR / filename
            avatar_file.save(save_path)
            avatar_path = f"/static/uploads/{filename}"

            with get_connection() as connection:
                connection.execute(
                    "INSERT INTO uploads (user_id, filename, path, uploaded_at) VALUES (?, ?, ?, ?)",
                    (user["id"], filename, avatar_path, datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")),
                )
                connection.commit()

        with get_connection() as connection:
            connection.execute(
                "UPDATE users SET bio = ?, avatar = ? WHERE id = ?",
                (bio, avatar_path, user["id"]),
            )
            connection.commit()

        flash("Profile updated.", "success")
        return redirect(url_for("profile.view_profile", username=user["username"]))

    return render_template("profile_edit.html", user=user, csrf_token=generate_csrf_token())


@profile_bp.route("/settings", methods=["GET"])
@login_required
def settings():
    user = current_user()
    return render_template("settings.html", user=user, csrf_token=generate_csrf_token())


@profile_bp.route("/settings/change-email", methods=["POST"])
@login_required
def change_email():
    user = current_user()
    if not validate_csrf():
        flash("Invalid CSRF token.", "danger")
        return redirect(url_for("profile.settings"))

    email = request.form.get("email", "").strip()
    confirm_password = request.form.get("confirm_password", "").strip()

    if confirm_password != user["password"]:
        flash("Password confirmation failed.", "danger")
        return redirect(url_for("profile.settings"))

    session["pending_email"] = email
    flash("Pending email captured. Complete verification to finalize the change.", "info")
    return redirect(url_for("profile.settings"))


@profile_bp.route("/settings/verify-email", methods=["POST"])
@login_required
def verify_email():
    user = current_user()
    current_email = user["email"]
    new_email = request.form.get("email", "").strip() or session.get("pending_email", "")

    if not new_email:
        flash("No email awaiting verification.", "warning")
        return redirect(url_for("profile.settings"))

    with get_connection() as connection:
        connection.execute(
            "UPDATE users SET email = ?, email_verified = 1 WHERE id = ?",
            (new_email, user["id"]),
        )
        connection.execute(
            "UPDATE mail_messages SET recipient_email = ? WHERE recipient_email = ?",
            (new_email, current_email),
        )
        connection.commit()

    session.pop("pending_email", None)
    flash("Email address verified and updated.", "success")
    return redirect(url_for("profile.settings"))


@profile_bp.route("/mailbox")
@login_required
def mailbox():
    user = current_user()
    with get_connection() as connection:
        messages = connection.execute(
            """
            SELECT subject, body, created_at
            FROM mail_messages
            WHERE recipient_email = ?
            ORDER BY id DESC
            """,
            (user["email"],),
        ).fetchall()
    return render_template("mailbox.html", user=user, messages=messages)
