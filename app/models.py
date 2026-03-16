from typing import Any

from app.database import get_connection


def fetch_user_by_id(user_id: int) -> Any:
    with get_connection() as connection:
        return connection.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()


def fetch_user_by_username(username: str) -> Any:
    with get_connection() as connection:
        return connection.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()


def fetch_post(post_id: int) -> Any:
    with get_connection() as connection:
        return connection.execute(
            """
            SELECT posts.*, users.username
            FROM posts
            JOIN users ON users.id = posts.author_id
            WHERE posts.id = ?
            """,
            (post_id,),
        ).fetchone()
