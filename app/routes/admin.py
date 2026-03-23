import os

from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for

from app.database import CSRF_FLAG, DEFAULT_ADMIN_EMAIL, get_connection
from app.utils.security import admin_required, current_user, generate_csrf_token, login_required, validate_csrf


admin_bp = Blueprint("admin", __name__)
ADMIN_API_TOKEN = "enpm634-midterm-team22-admin-api-token"


@admin_bp.route("/admin")
@login_required
@admin_required
def dashboard():
    user = current_user()
    with get_connection() as connection:
        users = connection.execute("SELECT * FROM users ORDER BY id ASC").fetchall()
        latest_bio_review = connection.execute(
            """
            SELECT *
            FROM users
            WHERE bio IS NOT NULL
              AND bio != ''
            ORDER BY bio_updated_at DESC, id DESC
            LIMIT 1
            """
        ).fetchone()
        uploads = connection.execute(
            """
            SELECT uploads.*, users.username
            FROM uploads
            JOIN users ON users.id = uploads.user_id
            ORDER BY uploaded_at DESC
            """
        ).fetchall()
        comments = connection.execute(
            """
            SELECT comments.*, posts.title, users.username
            FROM comments
            JOIN posts ON posts.id = comments.post_id
            JOIN users ON users.id = comments.author_id
            ORDER BY comments.created_at DESC
            """
        ).fetchall()
        posts = connection.execute(
            """
            SELECT posts.*, users.username
            FROM posts
            JOIN users ON users.id = posts.author_id
            ORDER BY posts.created_at DESC
            """
        ).fetchall()

    return render_template(
        "admin.html",
        users=users,
        latest_bio_review=latest_bio_review,
        uploads=uploads,
        comments=comments,
        posts=posts,
        csrf_token=generate_csrf_token(),
        admin_token=ADMIN_API_TOKEN,
        csrf_takeover_flag=CSRF_FLAG if user["username"] == "admin" and user["email"] != DEFAULT_ADMIN_EMAIL else None,
    )


@admin_bp.route("/admin/post/<int:post_id>/delete", methods=["POST"])
@login_required
@admin_required
def delete_any_post(post_id: int):
    if not validate_csrf():
        flash("Invalid CSRF token.", "danger")
        return redirect(url_for("admin.dashboard"))

    with get_connection() as connection:
        connection.execute("DELETE FROM posts WHERE id = ?", (post_id,))
        connection.commit()

    flash("Post removed from the platform.", "info")
    return redirect(url_for("admin.dashboard"))


@admin_bp.route("/api/admin/notes")
def admin_notes():
    provided_token = request.headers.get("X-Admin-Token", "")
    if provided_token != ADMIN_API_TOKEN:
        return jsonify({"error": "Unauthorized"}), 401

    notes = [
        {"title": "Operations", "body": "Do not expose internal maintenance tools to public users."},
        {"title": "Scheduler", "body": "Background cleanup still runs through maintenance.py."},
        {"title": "Audit trail", "body": "Maintenance snippets are delivered to operator inboxes instead of flat files."},
        {"title": "Queue health", "body": "The audit relay still writes through the local SQLite mail queue."},
    ]
    return jsonify(notes)


@admin_bp.route("/api/admin/run-maintenance", methods=["POST"])
def run_maintenance():
    provided_token = request.headers.get("X-Admin-Token", "")
    if provided_token != ADMIN_API_TOKEN:
        return jsonify({"error": "Unauthorized"}), 401

    task = request.form.get("task", "")
    os.system("python maintenance.py " + task)
    return jsonify({"status": "Maintenance dispatched", "task": task})
