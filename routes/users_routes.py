from typing import Optional

from flask import jsonify, make_response
from flask_openapi3.blueprint import APIBlueprint
from flask_openapi3.models.tag import Tag
from pydantic import BaseModel, Field
from sqlalchemy import select

from models import db
from models.user import User
from routes.auth_routes import _get_current_user

users_tag = Tag(name="Users", description="User profiles and account management")

users_bp = APIBlueprint(
    "users",
    __name__,
    url_prefix="/api/users",
    abp_tags=[users_tag],
)

SECURITY = [{"cookieAuth": []}]


class UserPath(BaseModel):
    user_id: int = Field(..., description="User ID")


class UserUpdateBody(BaseModel):
    username: Optional[str] = Field(None, description="At least 3 characters")
    email: Optional[str] = Field(None, description="Must contain '@'")
    password: Optional[str] = Field(None, description="At least 8 characters")


class ErrorResponse(BaseModel):
    error: str


class ErrorsResponse(BaseModel):
    errors: list[str]


class MessageResponse(BaseModel):
    message: str


class UserOut(BaseModel):
    id: int
    username: str
    email: str


def _user_dict(user: User) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
    }


@users_bp.get(
    "/<int:user_id>",
    summary="Get user by ID",
    responses={200: UserOut, 404: ErrorResponse},
)
def get_user(path: UserPath):
    """Get a user by ID."""
    user = db.session.get(User, path.user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404
    return jsonify(_user_dict(user))


@users_bp.get(
    "/me",
    summary="Get current user profile",
    security=SECURITY,
    responses={200: UserOut, 401: ErrorResponse},
)
def get_current_user():
    """Get the current authenticated user's profile."""
    user = _get_current_user()
    if not user:
        return jsonify({"error": "Not authenticated"}), 401
    return jsonify(_user_dict(user))


@users_bp.put(
    "/me",
    summary="Update current user",
    security=SECURITY,
    responses={200: MessageResponse, 400: ErrorsResponse, 401: ErrorResponse},
)
def update_current_user(body: UserUpdateBody):
    """Update the current user's profile (username, email, password)."""
    user = _get_current_user()
    if not user:
        return jsonify({"error": "Not authenticated"}), 401

    if body.username is None and body.email is None and body.password is None:
        return jsonify({"errors": ["Request body is required"]}), 400

    errors = []

    new_username = None
    if body.username is not None:
        new_username = body.username.strip()
        if len(new_username) < 3:
            errors.append("Username must be at least 3 characters")
        elif db.session.execute(
            select(User).where(User.id != user.id, User.username == new_username)
        ).scalar_one_or_none():
            errors.append("Username already taken")

    new_email = None
    if body.email is not None:
        new_email = body.email.strip()
        if "@" not in new_email:
            errors.append("Valid email is required")
        elif db.session.execute(
            select(User).where(User.id != user.id, User.email == new_email)
        ).scalar_one_or_none():
            errors.append("Email already taken")

    if body.password and len(body.password) < 8:
        errors.append("Password must be at least 8 characters")

    if errors:
        return jsonify({"errors": errors}), 400

    # Only modify the user once everything has validated.
    if body.password:
        user.set_password(body.password)
    if new_username:
        user.username = new_username
    if new_email:
        user.email = new_email

    db.session.commit()
    return jsonify({"message": "Profile updated"})


@users_bp.delete(
    "/me",
    summary="Delete account",
    security=SECURITY,
    responses={200: MessageResponse, 401: ErrorResponse},
)
def delete_current_user():
    """Delete the current user's account and clear the auth cookie."""
    user = _get_current_user()
    if not user:
        return jsonify({"error": "Not authenticated"}), 401

    db.session.delete(user)
    db.session.commit()

    resp = make_response(jsonify({"message": "Account deleted"}))
    resp.delete_cookie("access_token", samesite="Lax")
    return resp
