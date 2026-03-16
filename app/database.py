import os
import sqlite3
from datetime import datetime
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
DB_PATH = Path(os.environ.get("DB_PATH", ROOT_DIR / "database" / "enpm634_midterm_team22.db"))
INIT_SQL = ROOT_DIR / "database" / "init.sql"
UPLOAD_DIR = ROOT_DIR / "app" / "static" / "uploads"
DEFAULT_ADMIN_EMAIL = "admin@team22.local"
PUBLIC_MAILDROP_DOMAIN = "@maildrop.local"
ADMIN_PASSWORD = "ENPM634-admin-T22-4f9c2d7b"
OPSADMIN_PASSWORD = "ENPM634-ops-T22-8d1f6a4c"
STORED_XSS_FLAG = "ENPM634{stored_xss_comment}"
BLIND_SQLI_FLAG = "ENPM634{blind_sqli_extraction}"
BLIND_SQLI_FLAG_KEY = "search_archive"
IDOR_FLAG = "ENPM634{idor_draft_access}"
CSRF_FLAG = "ENPM634{csrf_account_takeover}"
FULL_CHAIN_FLAG = "ENPM634{full_chain_rce}"
FINAL_CHAIN_MAILDROP = "ops-audit@maildrop.local"
STALE_RCE_FILENAME = "rce-flag.txt"


def get_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_database() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    with get_connection() as connection:
        with open(INIT_SQL, "r", encoding="utf-8") as sql_file:
            connection.executescript(sql_file.read())
        connection.commit()

        user_count = connection.execute("SELECT COUNT(*) AS total FROM users").fetchone()["total"]
        if user_count == 0:
            seed_database(connection)
        migrate_training_state(connection)

    default_avatar = UPLOAD_DIR / "default-avatar.png"
    if not default_avatar.exists():
        default_avatar.write_bytes(
            bytes.fromhex(
                "89504E470D0A1A0A0000000D49484452000000010000000108060000001F15C489"
                "0000000D49444154789C6360606060000000040001F61738550000000049454E44AE426082"
            )
        )


def seed_database(connection: sqlite3.Connection) -> None:
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    users = [
        ("admin", DEFAULT_ADMIN_EMAIL, ADMIN_PASSWORD, "Site administrator and editor.", "/static/uploads/default-avatar.png", 1, 1),
        ("opsadmin", "ops@team22.local", OPSADMIN_PASSWORD, "Operations owner for internal posts.", "/static/uploads/default-avatar.png", 1, 1),
        ("alice", "alice@example.com", "alicepass", "Security student and hobby blogger.", "/static/uploads/default-avatar.png", 0, 1),
        ("bob", "bob@example.com", "bobpass", "Writes about Flask and containers.", "/static/uploads/default-avatar.png", 0, 0),
    ]
    connection.executemany(
        """
        INSERT INTO users (username, email, password, bio, avatar, is_admin, email_verified)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        users,
    )

    posts = [
        ("Welcome to ENPM634_midterm-Team22", "This is the first post on the platform.", 1, now),
        ("Docker Notes", "Container builds are automatic in this demo environment.", 4, now),
        ("Campus Security Club", "We meet every Friday to practice web testing.", 3, now),
    ]
    connection.executemany(
        "INSERT INTO posts (title, content, author_id, created_at) VALUES (?, ?, ?, ?)",
        posts,
    )

    drafts = [
        (
            "Moderator checklist",
            "Review imports, user bios, and flagged comments before publishing.",
            1,
            0,
            now,
        ),
        (
            "Private admin planning",
            f"Hidden note for grading lab work: {IDOR_FLAG}",
            2,
            0,
            now,
        ),
        (
            "Alice draft",
            "Still polishing this write-up before I publish it.",
            3,
            0,
            now,
        ),
    ]
    connection.executemany(
        "INSERT INTO drafts (title, content, author_id, is_published, created_at) VALUES (?, ?, ?, ?, ?)",
        drafts,
    )

    connection.execute(
        "INSERT INTO uploads (user_id, filename, path, uploaded_at) VALUES (?, ?, ?, ?)",
        (1, "default-avatar.png", "/static/uploads/default-avatar.png", now),
    )
    connection.execute(
        "INSERT INTO challenge_flags (flag_key, flag_value) VALUES (?, ?)",
        (BLIND_SQLI_FLAG_KEY, BLIND_SQLI_FLAG),
    )
    connection.executemany(
        "INSERT INTO mail_messages (recipient_email, subject, body, created_at) VALUES (?, ?, ?, ?)",
        [
            (
                DEFAULT_ADMIN_EMAIL,
                "Welcome to ENPM634_midterm-Team22",
                "Your profile email is active in the training environment.",
                now,
            ),
            (
                "alice@example.com",
                "Welcome to ENPM634_midterm-Team22",
                "Your profile email is active in the training environment.",
                now,
            ),
            (
                "bob@example.com",
                "Welcome to ENPM634_midterm-Team22",
                "Your profile email is active in the training environment.",
                now,
            ),
        ],
    )
    connection.commit()


def migrate_training_state(connection: sqlite3.Connection) -> None:
    stale_flag_file = UPLOAD_DIR / STALE_RCE_FILENAME
    if stale_flag_file.exists():
        stale_flag_file.unlink()

    admin = connection.execute("SELECT id, password, email FROM users WHERE username = 'admin'").fetchone()
    if admin and admin["password"] in {"admin123", BLIND_SQLI_FLAG}:
        connection.execute(
            "UPDATE users SET password = ? WHERE id = ?",
            (ADMIN_PASSWORD, admin["id"]),
        )

    ops_admin = connection.execute("SELECT id, password FROM users WHERE username = 'opsadmin'").fetchone()
    if ops_admin and ops_admin["password"] in {"opsadmin123", BLIND_SQLI_FLAG}:
        connection.execute(
            "UPDATE users SET password = ? WHERE id = ?",
            (OPSADMIN_PASSWORD, ops_admin["id"]),
        )

    challenge_flag = connection.execute(
        "SELECT id FROM challenge_flags WHERE flag_key = ?",
        (BLIND_SQLI_FLAG_KEY,),
    ).fetchone()
    if challenge_flag:
        connection.execute(
            "UPDATE challenge_flags SET flag_value = ? WHERE flag_key = ?",
            (BLIND_SQLI_FLAG, BLIND_SQLI_FLAG_KEY),
        )
    else:
        connection.execute(
            "INSERT INTO challenge_flags (flag_key, flag_value) VALUES (?, ?)",
            (BLIND_SQLI_FLAG_KEY, BLIND_SQLI_FLAG),
        )

    draft = connection.execute(
        "SELECT id FROM drafts WHERE title = 'Private admin planning'"
    ).fetchone()
    if draft:
        connection.execute(
            "UPDATE drafts SET content = ?, author_id = ? WHERE id = ?",
            (f"Hidden note for grading lab work: {IDOR_FLAG}", 2, draft["id"]),
        )

    connection.execute(
        """
        DELETE FROM mail_messages
        WHERE subject = 'Instructor flag'
           OR body LIKE ?
           OR body LIKE ?
           OR recipient_email = ?
        """,
        (f"%{CSRF_FLAG}%", f"%{FULL_CHAIN_FLAG}%", FINAL_CHAIN_MAILDROP),
    )

    admin_email = admin["email"] if admin else DEFAULT_ADMIN_EMAIL
    mailbox_count = connection.execute(
        "SELECT COUNT(*) AS total FROM mail_messages WHERE recipient_email = ?",
        (admin_email,),
    ).fetchone()["total"]
    if mailbox_count == 0:
        now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        connection.executemany(
            "INSERT INTO mail_messages (recipient_email, subject, body, created_at) VALUES (?, ?, ?, ?)",
            [
                (
                    admin_email,
                    "Welcome to ENPM634_midterm-Team22",
                    "Your profile email is active in the training environment.",
                    now,
                ),
            ],
        )

    connection.commit()
