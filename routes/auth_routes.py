from datetime import UTC, datetime, timedelta

from flask import Blueprint, jsonify, make_response, request
from jose import JWTError, jwt
from sqlalchemy import select

from models import db
from models.user import User

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")


def _encode_token(payload: dict) -> str:
    secret = __import__("os").environ.get("JWT_SECRET", "change-me-in-production")
    payload["exp"] = datetime.now(UTC) + timedelta(days=1)
    return jwt.encode(payload, secret, algorithm="HS256")


def _decode_token(token: str) -> dict | None:
    try:
        secret = __import__("os").environ.get("JWT_SECRET", "change-me-in-production")
        return jwt.decode(token, secret, algorithms=["HS256"])
    except JWTError as e:
        print(f"[DEBUG] JWTError: {e}")
        return None


def _get_current_user() -> User | None:
    cookie = request.cookies.get("jwt_token")
    print(f"[DEBUG] cookie = {cookie}")
    if not cookie:
        print("[DEBUG] no cookie found")
        return None
    payload = _decode_token(cookie)
    print(f"[DEBUG] decoded payload = {payload}")
    if not payload:
        print("[DEBUG] token decode failed")
        return None
    user = db.session.get(User, int(payload["sub"]))
    print(f"[DEBUG] fetched user = {user}")
    return user


@auth_bp.route("/register", methods=["POST"])
def register():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body is required"}), 400

    username = data.get("username", "").strip()
    email = data.get("email", "").strip()
    password = data.get("password", "")

    errors = []
    if not username or len(username) < 3:
        errors.append("Username must be at least 3 characters")
    if not email or "@" not in email:
        errors.append("Valid email is required")
    if not password or len(password) < 8:
        errors.append("Password must be at least 8 characters")

    if errors:
        return jsonify({"errors": errors}), 400

    existing = db.session.execute(
        select(User).where((User.username == username) | (User.email == email))
    ).scalar_one_or_none()
    if existing:
        return jsonify({"error": "Username or email already taken"}), 409

    user = User(username=username, email=email)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()

    token = _encode_token({"sub": str(user.id)})
    resp = make_response(
        jsonify(
            {
                "message": "Registration successful",
                "user": {
                    "id": user.id,
                    "username": user.username,
                    "email": user.email,
                },
            }
        )
    )
    resp.set_cookie("jwt_token", token, httponly=True, samesite="Lax", max_age=86400)
    return resp, 201


@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body is required"}), 400

    username_or_email = data.get("username", "").strip()
    password = data.get("password", "")

    if not username_or_email or not password:
        return jsonify({"errors": ["Username/email and password are required"]}), 400

    user = db.session.execute(
        select(User).where(
            (User.username == username_or_email) | (User.email == username_or_email)
        )
    ).scalar_one_or_none()

    if not user or not user.check_password(password):
        return jsonify({"error": "Invalid credentials"}), 401

    token = _encode_token({"sub": str(user.id)})
    resp = make_response(
        jsonify(
            {
                "message": "Login successful",
                "user": {
                    "id": user.id,
                    "username": user.username,
                    "email": user.email,
                },
            }
        )
    )
    resp.set_cookie("jwt_token", token, httponly=True, samesite="Lax", max_age=86400)
    return resp


@auth_bp.route("/logout", methods=["POST"])
def logout():
    resp = make_response(jsonify({"message": "Logged out"}))
    resp.delete_cookie("jwt_token", samesite="Lax")
    return resp


@auth_bp.route("/me", methods=["GET"])
def me():
    user = _get_current_user()
    if not user:
        return jsonify({"error": "Not authenticated"}), 401
    return jsonify(
        {
            "id": user.id,
            "username": user.username,
            "email": user.email,
        }
    )
