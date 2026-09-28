import logging
import os
from datetime import UTC, datetime, timedelta
from typing import Any, Optional

from flask import jsonify, make_response, request
from flask_openapi3.blueprint import APIBlueprint
from flask_openapi3.models.tag import Tag
from jose import JWTError, jwt
from pydantic import BaseModel, Field
from sqlalchemy import select

from models import db
from models.user import User

logger = logging.getLogger(__name__)

auth_tag = Tag(name="Auth", description="Registration, login and session handling")

auth_bp = APIBlueprint(
    "auth",
    __name__,
    url_prefix="/api/auth",
    abp_tags=[auth_tag],
)

SECURITY = [{"cookieAuth": []}]

COOKIE_NAME = "jwt_token"


class RegisterBody(BaseModel):
    username: str = Field(..., description="At least 3 characters")
    email: str = Field(..., description="Must contain '@'")
    password: str = Field(..., description="At least 8 characters")


class LoginBody(BaseModel):
    username: str = Field(..., description="Username or email")
    password: str


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


class AuthSuccessResponse(BaseModel):
    message: str
    user: UserOut


class MeResponse(BaseModel):
    id: int
    username: str
    email: str
    wishlist_public: Optional[bool] = None


def _encode_token(payload: dict) -> str:
    secret = os.environ.get("JWT_SECRET", "change-me-in-production")
    payload["exp"] = datetime.now(UTC) + timedelta(days=1)
    return jwt.encode(payload, secret, algorithm="HS256")


def _decode_token(token: str) -> dict | None:
    try:
        secret = os.environ.get("JWT_SECRET", "change-me-in-production")
        return jwt.decode(token, secret, algorithms=["HS256"])
    except JWTError as e:
        logger.debug("JWTError: %s", e)
        return None


def _get_current_user() -> User | None:
    cookie = request.cookies.get(COOKIE_NAME)
    if not cookie:
        logger.debug("no auth cookie found")
        return None
    payload = _decode_token(cookie)
    if not payload:
        logger.debug("token decode failed")
        return None
    user = db.session.get(User, int(payload["sub"]))
    logger.debug("fetched user = %s", user)
    return user


def _set_auth_cookie(resp, user: User):
    token = _encode_token({"sub": str(user.id)})
    resp.set_cookie(COOKIE_NAME, token, httponly=True, samesite="Lax", max_age=86400)


@auth_bp.post(
    "/register",
    summary="Register a new user",
    responses={
        201: AuthSuccessResponse,
        400: ErrorsResponse,
        409: ErrorResponse,
    },
)
def register(body: RegisterBody):
    """Register a new user account and set the auth cookie."""
    username = body.username.strip()
    email = body.email.strip()
    password = body.password

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
    _set_auth_cookie(resp, user)
    return resp, 201


@auth_bp.post(
    "/login",
    summary="Login",
    responses={
        200: AuthSuccessResponse,
        400: ErrorsResponse,
        401: ErrorResponse,
    },
)
def login(body: LoginBody):
    """Authenticate with username or email and set the auth cookie."""
    username_or_email = body.username.strip()
    password = body.password

    if not username_or_email or not password:
        return jsonify({"errors": ["Username/email and password are required"]}), 400

    user = db.session.execute(
        select(User).where(
            (User.username == username_or_email) | (User.email == username_or_email)
        )
    ).scalar_one_or_none()

    if not user or not user.check_password(password):
        return jsonify({"error": "Invalid credentials"}), 401

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
    _set_auth_cookie(resp, user)
    return resp


@auth_bp.post(
    "/logout",
    summary="Logout",
    responses={200: MessageResponse},
)
def logout():
    """Clear the JWT cookie and log out."""
    resp = make_response(jsonify({"message": "Logged out"}))
    resp.delete_cookie(COOKIE_NAME, samesite="Lax")
    return resp


@auth_bp.get(
    "/me",
    summary="Get current user",
    security=SECURITY,
    responses={200: MeResponse, 401: ErrorResponse},
)
def me():
    """Get the current authenticated user's info."""
    user = _get_current_user()
    if not user:
        return jsonify({"error": "Not authenticated"}), 401
    return jsonify(
        {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "wishlist_public": user.wishlist_public,
        }
    )
