import json
import logging
import urllib.parse
import urllib.request
import urllib.error

from flask import Blueprint, jsonify, request

logger = logging.getLogger(__name__)
from sqlalchemy import select

from models import db
from models.user import User
from models.wishlist_item import WishlistItem
from routes.auth_routes import _get_current_user

wishlist_bp = Blueprint("wishlist", __name__, url_prefix="/api/wishlist")

CHEAPSHARK_SEARCH_URL = "https://www.cheapshark.com/api/1.0/games"
CHEAPSHARK_GAME_URL = "https://www.cheapshark.com/api/1.0/games"


def _search_cheapshark(query: str) -> list[dict] | None:
    if not query or len(query.strip()) < 2:
        return []

    url = f"{CHEAPSHARK_SEARCH_URL}?title={urllib.parse.quote(query.strip())}"

    try:
        req = urllib.request.Request(
            url, headers={"User-Agent": "DealHunter/1.0 (contact@example.com)"}
        )
        with urllib.request.urlopen(req, timeout=15) as response:
            if response.status == 200:
                data = json.loads(response.read().decode())
                return data if isinstance(data, list) else []
    except urllib.error.URLError as e:
        logger.error(f"CheapShark URLError: {e.reason}")
    except json.JSONDecodeError as e:
        logger.error(f"CheapShark JSON decode error: {e}")
    except Exception as e:
        logger.error(f"CheapShark search error: {type(e).__name__}: {e}")

    return None


def _get_game_details(cheapshark_id: str) -> dict | None:
    if not cheapshark_id or not cheapshark_id.strip():
        return None

    url = f"{CHEAPSHARK_GAME_URL}?gameID={urllib.parse.quote(cheapshark_id.strip())}"

    try:
        req = urllib.request.Request(
            url, headers={"User-Agent": "DealHunter/1.0 (contact@example.com)"}
        )
        with urllib.request.urlopen(req, timeout=15) as response:
            if response.status == 200:
                data = json.loads(response.read().decode())
                return data if isinstance(data, dict) else None
    except urllib.error.URLError as e:
        logger.error(f"CheapShark game lookup URLError for {cheapshark_id}: {e.reason}")
    except json.JSONDecodeError as e:
        logger.error(f"CheapShark JSON decode error for {cheapshark_id}: {e}")
    except Exception as e:
        logger.error(
            f"CheapShark game lookup error for {cheapshark_id}: {type(e).__name__}: {e}"
        )

    return None


@wishlist_bp.route("/search", methods=["GET"], strict_slashes=False)
def search_games():
    query = request.args.get("q", "").strip()

    if not query or len(query) < 2:
        return jsonify({"error": "Search query must be at least 2 characters"}), 400

    results = _search_cheapshark(query)

    if results is None:
        return jsonify({"error": "Failed to search games"}), 500

    formatted = []
    for game in results[:30]:
        formatted.append(
            {
                "gameID": game.get("gameID", ""),
                "title": game.get("external", ""),
                "thumb": game.get("thumb", ""),
            }
        )

    return jsonify({"games": formatted})


@wishlist_bp.route("/", methods=["GET"], strict_slashes=False)
def get_wishlist():
    user = _get_current_user()
    if not user:
        return jsonify({"error": "Not authenticated"}), 401

    items = (
        db.session.execute(
            select(WishlistItem)
            .where(WishlistItem.user_id == user.id)
            .order_by(WishlistItem.created_at.desc())
        )
        .scalars()
        .all()
    )

    return jsonify(
        {
            "items": [
                {
                    "id": item.id,
                    "cheapshark_id": item.cheapshark_id,
                    "title": item.title,
                    "thumb": item.thumb,
                    "notes": item.notes,
                    "created_at": item.created_at.isoformat(),
                }
                for item in items
            ]
        }
    )


@wishlist_bp.route("/", methods=["POST"], strict_slashes=False)
def add_to_wishlist():
    user = _get_current_user()
    if not user:
        return jsonify({"error": "Not authenticated"}), 401

    data = request.get_json()
    if not data:
        return jsonify({"errors": ["Request body is required"]}), 400

    cheapshark_id = str(data.get("cheapshark_id", "")).strip()
    title = str(data.get("title", "")).strip()
    thumb = str(data.get("thumb", "")).strip()
    notes = str(data.get("notes", "")).strip()

    if not cheapshark_id or not title:
        return jsonify({"errors": ["cheapshark_id and title are required"]}), 400

    existing = db.session.execute(
        select(WishlistItem).where(
            WishlistItem.user_id == user.id, WishlistItem.cheapshark_id == cheapshark_id
        )
    ).scalar_one_or_none()

    if existing:
        return jsonify({"error": "Game already in wishlist"}), 409

    item = WishlistItem(
        user_id=user.id,
        cheapshark_id=cheapshark_id,
        title=title,
        thumb=thumb,
        notes=notes,
    )
    db.session.add(item)
    db.session.commit()

    return jsonify(
        {
            "message": "Added to wishlist",
            "item": {
                "id": item.id,
                "cheapshark_id": item.cheapshark_id,
                "title": item.title,
                "thumb": item.thumb,
                "notes": item.notes,
            },
        }
    ), 201


@wishlist_bp.route("/<int:item_id>", methods=["DELETE"], strict_slashes=False)
def remove_from_wishlist(item_id: int):
    user = _get_current_user()
    if not user:
        return jsonify({"error": "Not authenticated"}), 401

    item = db.session.get(WishlistItem, item_id)
    if not item:
        return jsonify({"error": "Wishlist item not found"}), 404

    if item.user_id != user.id:
        return jsonify({"error": "Not your wishlist item"}), 403

    db.session.delete(item)
    db.session.commit()

    return jsonify({"message": "Removed from wishlist"})


@wishlist_bp.route("/<int:item_id>", methods=["PUT"], strict_slashes=False)
def update_wishlist_item(item_id: int):
    user = _get_current_user()
    if not user:
        return jsonify({"error": "Not authenticated"}), 401

    item = db.session.get(WishlistItem, item_id)
    if not item:
        return jsonify({"error": "Wishlist item not found"}), 404

    if item.user_id != user.id:
        return jsonify({"error": "Not your wishlist item"}), 403

    data = request.get_json()
    if not data:
        return jsonify({"errors": ["Request body is required"]}), 400

    errors = []

    if "notes" in data:
        notes = str(data["notes"]).strip()
        if len(notes) > 500:
            errors.append("Notes must be under 500 characters")

    if errors:
        return jsonify({"errors": errors}), 400

    if "notes" in data:
        item.notes = str(data["notes"]).strip()

    db.session.commit()

    return jsonify(
        {
            "message": "Updated",
            "item": {
                "id": item.id,
                "cheapshark_id": item.cheapshark_id,
                "title": item.title,
                "thumb": item.thumb,
                "notes": item.notes,
            },
        }
    )


@wishlist_bp.route("/visibility", methods=["PUT"], strict_slashes=False)
def update_visibility():
    user = _get_current_user()
    if not user:
        return jsonify({"error": "Not authenticated"}), 401

    data = request.get_json()
    if not data:
        return jsonify({"errors": ["Request body is required"]}), 400

    public = data.get("public")
    if public is None or not isinstance(public, bool):
        return jsonify(
            {"errors": ["'public' boolean is required (true or false)"]}
        ), 400

    user.wishlist_public = public
    db.session.commit()

    return jsonify(
        {
            "message": "Visibility updated",
            "wishlist_public": user.wishlist_public,
        }
    )


@wishlist_bp.route("/user/<string:username>", methods=["GET"], strict_slashes=False)
def get_user_wishlist(username: str):
    target_user = db.session.execute(
        select(User).where(User.username == username)
    ).scalar_one_or_none()

    if not target_user:
        return jsonify({"error": "User not found"}), 404

    if not target_user.wishlist_public:
        return jsonify({"error": "This wishlist is private"}), 403

    items = (
        db.session.execute(
            select(WishlistItem)
            .where(WishlistItem.user_id == target_user.id)
            .order_by(WishlistItem.created_at.desc())
        )
        .scalars()
        .all()
    )

    return jsonify(
        {
            "username": target_user.username,
            "items": [
                {
                    "id": item.id,
                    "cheapshark_id": item.cheapshark_id,
                    "title": item.title,
                    "thumb": item.thumb,
                    "notes": item.notes,
                    "created_at": item.created_at.isoformat(),
                }
                for item in items
            ],
        }
    )


@wishlist_bp.route(
    "/game/<string:cheapshark_id>", methods=["GET"], strict_slashes=False
)
def get_game_details(cheapshark_id: str):
    details = _get_game_details(cheapshark_id)

    if not details:
        return jsonify({"error": "Game not found"}), 404

    deals = details.get("deals", [])
    cheapest_active = None
    cheapest_price_val = float("inf")

    for deal in deals:
        try:
            price = float(deal.get("price", "999"))
            if price < cheapest_price_val and price < float(
                deal.get("retailPrice", "0")
            ):
                cheapest_price_val = price
                cheapest_active = {
                    "storeID": deal.get("storeID"),
                    "dealID": deal.get("dealID"),
                    "price": deal.get("price"),
                    "retailPrice": deal.get("retailPrice"),
                    "savings": deal.get("savings"),
                }
        except (ValueError, TypeError):
            continue

    cheapest_ever = None
    ever_data = details.get("cheapestPriceEver")
    if ever_data:
        try:
            cheapest_ever = {
                "price": ever_data.get("price", "0"),
                "date": ever_data.get("date"),
            }
        except (ValueError, TypeError):
            pass

    return jsonify(
        {
            "info": details.get("info"),
            "cheapestActiveDeal": cheapest_active,
            "cheapestPriceEver": cheapest_ever,
        }
    )
