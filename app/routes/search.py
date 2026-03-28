from flask import Blueprint, render_template, request

from app.database import get_search_connection

search_bp = Blueprint("search", __name__)

# search for posts with matching title
@search_bp.route("/search")
def search():
    query = request.args.get("q", "").strip()
    results = []
    total = 0

    # query posts table for entries with matching title, ordered by creating time
    # code is vulnerable here, should have used parameterized query
    if query:
        sql = f"""
            SELECT id, title, content
            FROM posts
            WHERE title LIKE '%{query}%'
            ORDER BY created_at DESC
        """
        with get_search_connection() as connection:
            results = connection.execute(sql).fetchall()
            total = len(results)

    return render_template("search.html", query=query, results=results, total=total)
