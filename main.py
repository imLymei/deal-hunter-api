from flask import redirect
from flask_cors import CORS
from flask_openapi3.models.info import Info
from flask_openapi3.openapi import OpenAPI

from models import db
from routes.auth_routes import auth_bp
from routes.users_routes import users_bp


def create_app(database_uri: str | None = None) -> OpenAPI:
    app = OpenAPI(__name__, info=Info(title="DealHunter API", version="0.1.0"))

    if database_uri is not None:
        app.config["SQLALCHEMY_DATABASE_URI"] = database_uri
    else:
        app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///vault.db"

    db.init_app(app)

    with app.app_context():
        db.create_all()

    CORS(app, supports_credentials=True, origins=["http://localhost:3000"])

    app.register_blueprint(auth_bp)
    app.register_blueprint(users_bp)

    @app.route("/")
    def root() -> str:
        return "Hello World"

    @app.route("/docs")
    def docs_redirect():
        return redirect("/openapi/swagger", code=302)

    return app
