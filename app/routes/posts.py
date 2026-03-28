from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from app.database import STORED_XSS_FLAG, get_connection, sync_search_database
from app.models import fetch_post
from app.utils.security import current_user, generate_csrf_token, login_required, validate_csrf


posts_bp = Blueprint("posts", __name__)


@posts_bp.route("/")
def index():
    with get_connection() as connection:
        posts = connection.execute(
            """
            SELECT posts.*, users.username
            FROM posts
            JOIN users ON users.id = posts.author_id
            ORDER BY posts.created_at DESC
            """
        ).fetchall()
    return render_template("index.html", posts=posts)


@posts_bp.route("/post/<int:post_id>")
def view_post(post_id: int):
    user = current_user()
    with get_connection() as connection:
        post = connection.execute(
            """
            SELECT posts.*, users.username
            FROM posts
            JOIN users ON users.id = posts.author_id
            WHERE posts.id = ?
            """,
            (post_id,),
        ).fetchone()
        comments = connection.execute(
            """
            SELECT comments.*, users.username
            FROM comments
            JOIN users ON users.id = comments.author_id
            WHERE post_id = ?
            ORDER BY comments.created_at ASC
            """,
            (post_id,),
        ).fetchall()

    if not post:
        flash("Post not found.", "warning")
        return redirect(url_for("posts.index"))

    # submitted a comment with XSS-like content — flag is passed to template
    xss_training_ready = bool(user and session.get("comment_xss_post_id") == post_id)
    return render_template(
        "post_detail.html",
        post=post,
        comments=comments,
        csrf_token=generate_csrf_token(),
        xss_training_ready=xss_training_ready,
        xss_flag=STORED_XSS_FLAG if xss_training_ready else "",
    )


@posts_bp.route("/post/create", methods=["GET", "POST"])
@login_required
def create_post():
    user = current_user()
    if request.method == "POST":
        if not validate_csrf():
            flash("Invalid CSRF token.", "danger")
            return redirect(url_for("posts.create_post"))

        title = request.form.get("title", "").strip()
        content = request.form.get("content", "").strip()
        save_as_draft = request.form.get("save_as_draft")

        if save_as_draft:
            with get_connection() as connection:
                connection.execute(
                    """
                    INSERT INTO drafts (title, content, author_id, is_published, created_at)
                    VALUES (?, ?, ?, 0, ?)
                    """,
                    (title, content, user["id"], datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")),
                )
                connection.commit()
            flash("Draft saved successfully.", "success")
            return redirect(url_for("drafts.list_drafts"))

        with get_connection() as connection:
            connection.execute(
                "INSERT INTO posts (title, content, author_id, created_at) VALUES (?, ?, ?, ?)",
                (title, content, user["id"], datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")),
            )
            connection.commit()
        sync_search_database()

        flash("Post published.", "success")
        return redirect(url_for("posts.index"))

    return render_template("post_form.html", post=None, csrf_token=generate_csrf_token())


@posts_bp.route("/post/<int:post_id>/edit", methods=["GET", "POST"])
@login_required
def edit_post(post_id: int):
    user = current_user()
    post = fetch_post(post_id)
    if not post or post["author_id"] != user["id"]:
        flash("You can only edit your own posts.", "danger")
        return redirect(url_for("posts.index"))

    if request.method == "POST":
        if not validate_csrf():
            flash("Invalid CSRF token.", "danger")
            return redirect(url_for("posts.edit_post", post_id=post_id))

        title = request.form.get("title", "").strip()
        content = request.form.get("content", "").strip()

        with get_connection() as connection:
            connection.execute(
                "UPDATE posts SET title = ?, content = ? WHERE id = ?",
                (title, content, post_id),
            )
            connection.commit()
        sync_search_database()

        flash("Post updated.", "success")
        return redirect(url_for("posts.view_post", post_id=post_id))

    return render_template("post_form.html", post=post, csrf_token=generate_csrf_token())


@posts_bp.route("/post/<int:post_id>/delete", methods=["POST"])
@login_required
def delete_post(post_id: int):
    user = current_user()
    post = fetch_post(post_id)
    if not post or (post["author_id"] != user["id"] and not user["is_admin"]):
        flash("You do not have permission to delete that post.", "danger")
        return redirect(url_for("posts.index"))

    if not validate_csrf():
        flash("Invalid CSRF token.", "danger")
        return redirect(url_for("posts.view_post", post_id=post_id))

    with get_connection() as connection:
        connection.execute("DELETE FROM posts WHERE id = ?", (post_id,))
        connection.commit()
    sync_search_database()

    flash("Post deleted.", "info")
    return redirect(url_for("posts.index"))


@posts_bp.route("/post/<int:post_id>/comment", methods=["POST"])
@login_required
def add_comment(post_id: int):
    if not validate_csrf():
        flash("Invalid CSRF token.", "danger")
        return redirect(url_for("posts.view_post", post_id=post_id))

    user = current_user()
    comment_text = request.form.get("comment_text", "").strip()
    if not comment_text:
        flash("Comment text cannot be empty.", "danger")
        return redirect(url_for("posts.view_post", post_id=post_id))
        
    # Raw user input is stored directly into the database, enabling stored XSS
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO comments (post_id, author_id, comment_text, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (post_id, user["id"], comment_text, datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")),
        )
        connection.commit()

    # XSS pattern detection happens AFTER DB insert
    # Does NOT prevent the XSS, only detects it
    lowered_comment = comment_text.lower()
    if "<" in comment_text or "javascript:" in lowered_comment or "onerror" in lowered_comment or "onload" in lowered_comment:
        session["comment_xss_post_id"] = post_id

    flash("Comment added.", "success")
    return redirect(url_for("posts.view_post", post_id=post_id))
