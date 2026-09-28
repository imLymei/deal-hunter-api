from flask import redirect
from flask_cors import CORS
from flask_openapi3.models.info import Info
from flask_openapi3.openapi import OpenAPI

from models import db
from models.user import User  # noqa: F401
from models.wishlist_item import WishlistItem  # noqa: F401
from routes.auth_routes import auth_bp
from routes.users_routes import users_bp
from routes.wishlist_routes import wishlist_bp


def create_app(database_uri: str | None = None) -> OpenAPI:
    app = OpenAPI(__name__, info=Info(title="DealHunter API", version="0.1.0"))

    # Define cookie-based auth security scheme for Swagger UI
    app.config["OPENAPI"] = {
        "securitySchemes": {
            "cookieAuth": {
                "type": "apiKey",
                "in": "cookie",
                "name": "jwt_token",
                "description": "JWT token stored in httpOnly cookie",
            }
        }
    }

    if database_uri is not None:
        app.config["SQLALCHEMY_DATABASE_URI"] = database_uri
    else:
        app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///vault.db"

    db.init_app(app)

    with app.app_context():
        db.create_all()

    CORS(app, supports_credentials=True, origins=["http://localhost:3000"])

    app.register_api(auth_bp)
    app.register_api(users_bp)
    app.register_api(wishlist_bp)

    @app.route("/", strict_slashes=False)
    def root() -> str:
        return "Hello World"

    @app.route("/docs", strict_slashes=False)
    def docs_redirect():
        return redirect("/openapi/swagger", code=302)

    return app
