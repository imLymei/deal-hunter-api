from flask import Blueprint, jsonify, make_response, request
from sqlalchemy import select

from models import db
from models.user import User
from routes.auth_routes import _get_current_user

users_bp = Blueprint("users", __name__, url_prefix="/api/users")


@users_bp.route("/<int:user_id>", methods=["GET"], strict_slashes=False)
def get_user(user_id: int):
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404
    return jsonify(
        {
            "id": user.id,
            "username": user.username,
            "email": user.email,
        }
    )


@users_bp.route("/me", methods=["GET"], strict_slashes=False)
def get_current_user():
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


@users_bp.route("/me", methods=["PUT"], strict_slashes=False)
def update_current_user():
    user = _get_current_user()
    if not user:
        return jsonify({"error": "Not authenticated"}), 401

    data = request.get_json()
    if not data:
        return jsonify({"errors": ["Request body is required"]}), 400

    errors = []

    if "username" in data:
        new_username = data["username"].strip()
        if len(new_username) < 3:
            errors.append("Username must be at least 3 characters")
        elif db.session.execute(
            select(User).where(User.id != user.id, User.username == new_username)
        ).scalar_one_or_none():
            errors.append("Username already taken")

    if "email" in data:
        new_email = data["email"].strip()
        if "@" not in new_email:
            errors.append("Valid email is required")
        elif db.session.execute(
            select(User).where(User.id != user.id, User.email == new_email)
        ).scalar_one_or_none():
            errors.append("Email already taken")

    if data.get("password"):
        if len(data["password"]) < 8:
            errors.append("Password must be at least 8 characters")
        else:
            user.set_password(data["password"])

    if errors:
        return jsonify({"errors": errors}), 400

    if "username" in data and data["username"].strip():
        user.username = data["username"].strip()
    if "email" in data and data["email"].strip():
        user.email = data["email"].strip()

    db.session.commit()
    return jsonify({"message": "Profile updated"})


@users_bp.route("/me", methods=["DELETE"], strict_slashes=False)
def delete_current_user():
    user = _get_current_user()
    if not user:
        return jsonify({"error": "Not authenticated"}), 401

    db.session.delete(user)
    db.session.commit()

    resp = make_response(jsonify({"message": "Account deleted"}))
    resp.delete_cookie("access_token", samesite="Lax")
    return resp
