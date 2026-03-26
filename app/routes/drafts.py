from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for

from app.database import allocate_public_draft_id, get_connection
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
                INSERT INTO drafts (public_id, title, content, author_id, is_published, created_at)
                VALUES (?, ?, ?, ?, 0, ?)
                """,
                (
                    allocate_public_draft_id(connection),
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


# edit an existing draft
@drafts_bp.route("/draft/edit/<int:draft_id>", methods=["GET", "POST"])
@login_required
def edit_draft(draft_id: int):
    user = current_user()
    # grab the draft from the database
    with get_connection() as connection:
        draft = connection.execute(
            "SELECT * FROM drafts WHERE public_id = ?", (draft_id,)
        ).fetchone()

    # check if the draft exists and the user owns it
    if not draft or draft["author_id"] != user["id"]:
        flash("Draft not found.", "warning")
        return redirect(url_for("drafts.list_drafts"))

    if request.method == "POST":
        # check the CSRF token
        if not validate_csrf():
            flash("Invalid CSRF token.", "danger")
            return redirect(url_for("drafts.edit_draft", draft_id=draft_id))
        # save the updated title and content
        with get_connection() as connection:
            connection.execute(
                "UPDATE drafts SET title = ?, content = ? WHERE public_id = ?",
                (request.form.get("title", "").strip(), request.form.get("content", "").strip(), draft_id),
            )
            connection.commit()
        flash("Draft updated.", "success")
        return redirect(url_for("drafts.view_draft", draft_id=draft_id))

    # show the edit form with the current draft data
    return render_template("draft_form.html", draft=draft, csrf_token=generate_csrf_token())


# delete a draft
@drafts_bp.route("/draft/delete/<int:draft_id>", methods=["POST"])
@login_required
def delete_draft(draft_id: int):
    user = current_user()
    # check the CSRF token
    if not validate_csrf():
        flash("Invalid CSRF token.", "danger")
        return redirect(url_for("drafts.list_drafts"))

    with get_connection() as connection:
        # make sure the draft exists and the user owns it
        draft = connection.execute(
            "SELECT * FROM drafts WHERE public_id = ?", (draft_id,)
        ).fetchone()
        if not draft or draft["author_id"] != user["id"]:
            flash("Draft not found.", "warning")
            return redirect(url_for("drafts.list_drafts"))
        # remove it from the database
        connection.execute("DELETE FROM drafts WHERE public_id = ?", (draft_id,))
        connection.commit()

    flash("Draft deleted.", "success")
    return redirect(url_for("drafts.list_drafts"))


@drafts_bp.route("/draft/view/<int:draft_id>")
@login_required
def view_draft(draft_id: int):
    with get_connection() as connection:
        draft = connection.execute(
            """
            SELECT drafts.*, users.username
            FROM drafts
            JOIN users ON users.id = drafts.author_id
            WHERE drafts.public_id = ?
            """,
            (draft_id,),
        ).fetchone()

    if not draft:
        flash("Draft not found.", "warning")
        return redirect(url_for("drafts.list_drafts"))

    return render_template(
        "draft_view.html",
        draft=draft,
        csrf_token=generate_csrf_token(),
        publish_url=url_for("drafts.publish_draft", draft_id=draft["public_id"]),
    )


@drafts_bp.route("/draft/publish/<int:draft_id>", methods=["POST"])
@login_required
def publish_draft(draft_id: int):
    user = current_user()
    if not validate_csrf():
        flash("Invalid CSRF token.", "danger")
        return redirect(url_for("drafts.list_drafts"))

    with get_connection() as connection:
        draft = connection.execute("SELECT * FROM drafts WHERE public_id = ?", (draft_id,)).fetchone()
        if not draft or draft["author_id"] != user["id"]:
            flash("You can only publish your own drafts.", "danger")
            return redirect(url_for("drafts.list_drafts"))

        connection.execute(
            "INSERT INTO posts (title, content, author_id, created_at) VALUES (?, ?, ?, ?)",
            (draft["title"], draft["content"], user["id"], datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")),
        )
        connection.execute("UPDATE drafts SET is_published = 1 WHERE id = ?", (draft["id"],))
        connection.commit()

    flash("Draft published.", "success")
    return redirect(url_for("posts.index"))
