from flask import Flask

from app.database import init_database
from app.routes.admin import admin_bp
from app.routes.auth import auth_bp
from app.routes.drafts import drafts_bp
from app.routes.posts import posts_bp
from app.routes.profile import profile_bp
from app.routes.search import search_bp
from app.utils.security import current_user, generate_csrf_token


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["SECRET_KEY"] = "enpm634-midterm-team22-dev-secret"
    app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024

    init_database() # initialize database

    # register blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(posts_bp)
    app.register_blueprint(drafts_bp)
    app.register_blueprint(search_bp)
    app.register_blueprint(profile_bp)
    app.register_blueprint(admin_bp)

    @app.context_processor
    def inject_globals():
        return {"current_user": current_user(), "csrf_token_value": generate_csrf_token()}

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
