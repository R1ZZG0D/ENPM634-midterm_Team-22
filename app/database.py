import os
import sqlite3
from datetime import datetime
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
DB_PATH = Path(os.environ.get("DB_PATH", ROOT_DIR / "database" / "enpm634_midterm_team22.db"))
INIT_SQL = ROOT_DIR / "database" / "init.sql"
UPLOAD_DIR = ROOT_DIR / "app" / "static" / "uploads"
BLIND_SQLI_FLAG = "ENPM634{blind_sqli_extraction}"


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
        ("admin", "admin@team22.local", BLIND_SQLI_FLAG, "Site administrator and editor.", "/static/uploads/default-avatar.png", 1, 1),
        ("opsadmin", "ops@team22.local", "opsadmin123", "Operations owner for internal posts.", "/static/uploads/default-avatar.png", 1, 1),
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
            "Hidden note for grading lab work: ENPM634{idor_draft_access}",
            1,
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
    connection.executemany(
        "INSERT INTO mail_messages (recipient_email, subject, body, created_at) VALUES (?, ?, ?, ?)",
        [
            (
                "admin@team22.local",
                "Welcome to ENPM634_midterm-Team22",
                "Your profile email is active in the training environment.",
                now,
            ),
            (
                "admin@team22.local",
                "Instructor flag",
                "Admin mailbox retention key: ENPM634{csrf_account_takeover}",
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
    admin = connection.execute("SELECT id, password, email FROM users WHERE username = 'admin'").fetchone()
    if admin and admin["password"] == "admin123":
        connection.execute(
            "UPDATE users SET password = ? WHERE id = ?",
            (BLIND_SQLI_FLAG, admin["id"]),
        )

    ops_admin = connection.execute("SELECT id, password FROM users WHERE username = 'opsadmin'").fetchone()
    if ops_admin and ops_admin["password"] == BLIND_SQLI_FLAG:
        connection.execute(
            "UPDATE users SET password = ? WHERE id = ?",
            ("opsadmin123", ops_admin["id"]),
        )

    admin_email = admin["email"] if admin else "admin@team22.local"
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
                (
                    admin_email,
                    "Instructor flag",
                    "Admin mailbox retention key: ENPM634{csrf_account_takeover}",
                    now,
                ),
            ],
        )

    connection.commit()
