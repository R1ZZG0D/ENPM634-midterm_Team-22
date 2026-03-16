from flask import Blueprint, render_template, request

from app.database import get_connection


search_bp = Blueprint("search", __name__)


@search_bp.route("/search")
def search():
    query = request.args.get("q", "").strip()
    results = []
    total = 0

    if query:
        sql = f"""
            SELECT id, title, content
            FROM posts
            WHERE title LIKE '%{query}%'
            ORDER BY created_at DESC
        """
        with get_connection() as connection:
            results = connection.execute(sql).fetchall()
            total = len(results)

    return render_template("search.html", query=query, results=results, total=total)
