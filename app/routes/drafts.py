from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for

from app.database import get_connection
from app.utils.security import current_user, generate_csrf_token, login_required, validate_csrf


drafts_bp = Blueprint("drafts", __name__)


@drafts_bp.route("/drafts")
@login_required
def list_drafts():
    user = current_user()
    with get_connection() as connection:
        drafts = connection.execute(
            "SELECT * FROM drafts WHERE author_id = ? ORDER BY created_at DESC",
            (user["id"],),
        ).fetchall()
    return render_template("drafts.html", drafts=drafts, csrf_token=generate_csrf_token())


@drafts_bp.route("/draft/create", methods=["GET", "POST"])
@login_required
def create_draft():
    user = current_user()
    if request.method == "POST":
        if not validate_csrf():
            flash("Invalid CSRF token.", "danger")
            return redirect(url_for("drafts.create_draft"))

        with get_connection() as connection:
            connection.execute(
                """
                INSERT INTO drafts (title, content, author_id, is_published, created_at)
                VALUES (?, ?, ?, 0, ?)
                """,
                (
                    request.form.get("title", "").strip(),
                    request.form.get("content", "").strip(),
                    user["id"],
                    datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
                ),
            )
            connection.commit()
        flash("Draft created.", "success")
        return redirect(url_for("drafts.list_drafts"))

    return render_template("draft_form.html", csrf_token=generate_csrf_token())


@drafts_bp.route("/draft/view/<int:draft_id>")
@login_required
def view_draft(draft_id: int):
    with get_connection() as connection:
        draft = connection.execute(
            """
            SELECT drafts.*, users.username
            FROM drafts
            JOIN users ON users.id = drafts.author_id
            WHERE drafts.id = ?
            """,
            (draft_id,),
        ).fetchone()

    if not draft:
        flash("Draft not found.", "warning")
        return redirect(url_for("drafts.list_drafts"))

    return render_template("draft_view.html", draft=draft, csrf_token=generate_csrf_token())


@drafts_bp.route("/draft/publish/<int:draft_id>", methods=["POST"])
@login_required
def publish_draft(draft_id: int):
    user = current_user()
    if not validate_csrf():
        flash("Invalid CSRF token.", "danger")
        return redirect(url_for("drafts.list_drafts"))

    with get_connection() as connection:
        draft = connection.execute("SELECT * FROM drafts WHERE id = ?", (draft_id,)).fetchone()
        if not draft or draft["author_id"] != user["id"]:
            flash("You can only publish your own drafts.", "danger")
            return redirect(url_for("drafts.list_drafts"))

        connection.execute(
            "INSERT INTO posts (title, content, author_id, created_at) VALUES (?, ?, ?, ?)",
            (draft["title"], draft["content"], user["id"], datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")),
        )
        connection.execute("UPDATE drafts SET is_published = 1 WHERE id = ?", (draft_id,))
        connection.commit()

    flash("Draft published.", "success")
    return redirect(url_for("posts.index"))
