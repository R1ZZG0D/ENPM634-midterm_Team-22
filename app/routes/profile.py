from datetime import datetime
from html.parser import HTMLParser
import sqlite3
from urllib.parse import urlsplit

from flask import Blueprint, current_app, flash, redirect, render_template, request, session, url_for

from app.database import PUBLIC_MAILDROP_DOMAIN, UPLOAD_DIR, get_connection
from app.models import fetch_user_by_username
from app.utils.security import current_user, generate_csrf_token, login_required, validate_csrf


profile_bp = Blueprint("profile", __name__)


class AutoSubmitFormParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.form = None
        self._capture_form = False

    def handle_starttag(self, tag, attrs) -> None:
        attributes = dict(attrs)
        if (
            tag == "form"
            and self.form is None
            and attributes.get("data-training-autosubmit") == "true"
        ):
            self._capture_form = True
            self.form = {
                "action": attributes.get("action", ""),
                "method": attributes.get("method", "get").upper(),
                "inputs": {},
            }
            return

        if tag == "input" and self._capture_form and self.form is not None:
            name = attributes.get("name", "")
            if name:
                self.form["inputs"][name] = attributes.get("value", "")

    def handle_endtag(self, tag) -> None:
        if tag == "form" and self._capture_form:
            self._capture_form = False


def normalize_review_path(review_path: str) -> str:
    candidate = (review_path or "").strip()
    if not candidate:
        return ""

    parsed = urlsplit(candidate)
    if parsed.scheme and parsed.netloc:
        if parsed.netloc not in {"localhost:5000", "127.0.0.1:5000"}:
            return ""
        candidate = parsed.path
        if parsed.query:
            candidate = f"{candidate}?{parsed.query}"

    if not candidate.startswith("/") or candidate.startswith("//"):
        return ""

    return candidate


def run_admin_review(review_path: str) -> bool:
    target_path = normalize_review_path(review_path)
    if not target_path:
        return False

    with get_connection() as connection:
        admin = connection.execute(
            "SELECT id FROM users WHERE username = 'admin'"
        ).fetchone()

    if not admin:
        return False

    app = current_app._get_current_object()
    client = app.test_client()
    with client.session_transaction() as training_session:
        training_session["user_id"] = admin["id"]
        training_session["csrf_token"] = "review-bot"

    response = client.get(target_path, follow_redirects=True)
    parser = AutoSubmitFormParser()
    parser.feed(response.get_data(as_text=True))

    if not parser.form:
        return True

    action_path = normalize_review_path(parser.form["action"] or target_path)
    if not action_path:
        return False

    if parser.form["method"] == "POST":
        client.post(action_path, data=parser.form["inputs"], follow_redirects=True)
        return True

    client.get(action_path, query_string=parser.form["inputs"], follow_redirects=True)
    return True


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
                "UPDATE users SET bio = ?, bio_updated_at = ?, avatar = ? WHERE id = ?",
                (bio, datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"), avatar_path, user["id"]),
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

    try:
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
    except sqlite3.IntegrityError:
        flash("That email address is already assigned to another account.", "danger")
        return redirect(url_for("profile.settings"))

    session.pop("pending_email", None)
    flash("Email address verified and updated.", "success")
    return redirect(url_for("profile.settings"))


@profile_bp.route("/support/email-preview")
def support_email_preview():
    preview_email = request.args.get("email", "").strip().lower()
    return render_template("support_email_preview.html", preview_email=preview_email)


@profile_bp.route("/support/request-review", methods=["POST"])
@login_required
def request_review():
    if not validate_csrf():
        flash("Invalid CSRF token.", "danger")
        return redirect(url_for("profile.settings"))

    review_path = request.form.get("review_path", "")
    if not run_admin_review(review_path):
        flash("Only internal review paths can be queued.", "danger")
        return redirect(url_for("profile.settings"))

    flash("Support review queued for the requested page.", "success")
    return redirect(url_for("profile.settings"))


@profile_bp.route("/mailbox")
def mailbox():
    requested_email = request.args.get("email", "").strip().lower()
    public_maildrop = requested_email.endswith(PUBLIC_MAILDROP_DOMAIN)
    user = current_user()

    if public_maildrop:
        mailbox_email = requested_email
    else:
        if not user:
            flash("Please sign in to continue.", "warning")
            return redirect(url_for("auth.login"))
        mailbox_email = user["email"]

    with get_connection() as connection:
        messages = connection.execute(
            """
            SELECT subject, body, created_at
            FROM mail_messages
            WHERE recipient_email = ?
            ORDER BY id DESC
            """,
            (mailbox_email,),
        ).fetchall()
    return render_template(
        "mailbox.html",
        mailbox_email=mailbox_email,
        messages=messages,
        public_maildrop=public_maildrop,
    )
