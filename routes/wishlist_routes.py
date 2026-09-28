import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from typing import Optional

from flask import jsonify
from flask_openapi3.blueprint import APIBlueprint
from flask_openapi3.models.tag import Tag
from pydantic import BaseModel, Field, StrictBool
from sqlalchemy import select

from models import db
from models.user import User
from models.wishlist_item import WishlistItem
from routes.auth_routes import _get_current_user

logger = logging.getLogger(__name__)

wishlist_tag = Tag(name="Wishlist", description="Game wishlist and CheapShark lookups")

wishlist_bp = APIBlueprint(
    "wishlist",
    __name__,
    url_prefix="/api/wishlist",
    abp_tags=[wishlist_tag],
)

SECURITY = [{"cookieAuth": []}]

CHEAPSHARK_SEARCH_URL = "https://www.cheapshark.com/api/1.0/games"
CHEAPSHARK_GAME_URL = "https://www.cheapshark.com/api/1.0/games"


class SearchQuery(BaseModel):
    q: str = Field(..., min_length=2, description="Game title to search for")


class ItemPath(BaseModel):
    item_id: int = Field(..., description="Wishlist item ID")


class UsernamePath(BaseModel):
    username: str = Field(..., description="Username of the wishlist owner")


class GamePath(BaseModel):
    cheapshark_id: str = Field(..., description="CheapShark game ID")


class WishlistAddBody(BaseModel):
    cheapshark_id: str
    title: str
    thumb: str = ""
    notes: str = ""


class WishlistUpdateBody(BaseModel):
    notes: Optional[str] = Field(None, description="Max 500 characters")


class VisibilityBody(BaseModel):
    public: StrictBool


class ErrorResponse(BaseModel):
    error: str


class ErrorsResponse(BaseModel):
    errors: list[str]


class GameSearchResult(BaseModel):
    gameID: str
    title: str
    thumb: str


class SearchResponse(BaseModel):
    games: list[GameSearchResult]


class WishlistItemOut(BaseModel):
    id: int
    cheapshark_id: str
    title: str
    thumb: str
    notes: str
    created_at: Optional[str] = None


class WishlistResponse(BaseModel):
    items: list[WishlistItemOut]


class PublicWishlistResponse(BaseModel):
    username: str
    items: list[WishlistItemOut]


class ItemMessageResponse(BaseModel):
    message: str
    item: WishlistItemOut


class MessageResponse(BaseModel):
    message: str


class VisibilityResponse(BaseModel):
    message: str
    wishlist_public: bool


class ActiveDeal(BaseModel):
    storeID: Optional[str] = None
    dealID: Optional[str] = None
    price: Optional[str] = None
    retailPrice: Optional[str] = None
    savings: Optional[str] = None


class PriceEver(BaseModel):
    price: str
    date: Optional[int] = None


class GameDetailsResponse(BaseModel):
    info: Optional[dict] = None
    cheapestActiveDeal: Optional[ActiveDeal] = None
    cheapestPriceEver: Optional[PriceEver] = None


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

    url = f"{CHEAPSHARK_GAME_URL}?id={urllib.parse.quote(cheapshark_id.strip())}"

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


def _item_dict(item: WishlistItem, include_created: bool = False) -> dict:
    data = {
        "id": item.id,
        "cheapshark_id": item.cheapshark_id,
        "title": item.title,
        "thumb": item.thumb,
        "notes": item.notes,
    }
    if include_created:
        data["created_at"] = item.created_at.isoformat()
    return data


@wishlist_bp.get(
    "/search",
    summary="Search games",
    responses={200: SearchResponse, 400: ErrorResponse, 500: ErrorResponse},
)
def search_games(query: SearchQuery):
    """Search games via the CheapShark API."""
    q = query.q.strip()

    if len(q) < 2:
        return jsonify({"error": "Search query must be at least 2 characters"}), 400

    results = _search_cheapshark(q)

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


@wishlist_bp.get(
    "/",
    summary="Get own wishlist",
    security=SECURITY,
    responses={200: WishlistResponse, 401: ErrorResponse},
)
def get_wishlist():
    """Get the current user's wishlist items."""
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
        {"items": [_item_dict(item, include_created=True) for item in items]}
    )


@wishlist_bp.post(
    "/",
    summary="Add to wishlist",
    security=SECURITY,
    responses={
        201: ItemMessageResponse,
        400: ErrorsResponse,
        401: ErrorResponse,
        409: ErrorResponse,
    },
)
def add_to_wishlist(body: WishlistAddBody):
    """Add a game to the current user's wishlist."""
    user = _get_current_user()
    if not user:
        return jsonify({"error": "Not authenticated"}), 401

    cheapshark_id = body.cheapshark_id.strip()
    title = body.title.strip()
    thumb = body.thumb.strip()
    notes = body.notes.strip()

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

    return jsonify({"message": "Added to wishlist", "item": _item_dict(item)}), 201


@wishlist_bp.delete(
    "/<int:item_id>",
    summary="Remove from wishlist",
    security=SECURITY,
    responses={
        200: MessageResponse,
        401: ErrorResponse,
        403: ErrorResponse,
        404: ErrorResponse,
    },
)
def remove_from_wishlist(path: ItemPath):
    """Remove an item from the current user's wishlist."""
    user = _get_current_user()
    if not user:
        return jsonify({"error": "Not authenticated"}), 401

    item = db.session.get(WishlistItem, path.item_id)
    if not item:
        return jsonify({"error": "Wishlist item not found"}), 404

    if item.user_id != user.id:
        return jsonify({"error": "Not your wishlist item"}), 403

    db.session.delete(item)
    db.session.commit()

    return jsonify({"message": "Removed from wishlist"})


@wishlist_bp.put(
    "/<int:item_id>",
    summary="Update wishlist item",
    security=SECURITY,
    responses={
        200: ItemMessageResponse,
        400: ErrorsResponse,
        401: ErrorResponse,
        403: ErrorResponse,
        404: ErrorResponse,
    },
)
def update_wishlist_item(path: ItemPath, body: WishlistUpdateBody):
    """Update a wishlist item's notes."""
    user = _get_current_user()
    if not user:
        return jsonify({"error": "Not authenticated"}), 401

    item = db.session.get(WishlistItem, path.item_id)
    if not item:
        return jsonify({"error": "Wishlist item not found"}), 404

    if item.user_id != user.id:
        return jsonify({"error": "Not your wishlist item"}), 403

    if body.notes is None:
        return jsonify({"errors": ["Request body is required"]}), 400

    notes = body.notes.strip()
    if len(notes) > 500:
        return jsonify({"errors": ["Notes must be under 500 characters"]}), 400

    item.notes = notes
    db.session.commit()

    return jsonify({"message": "Updated", "item": _item_dict(item)})


@wishlist_bp.put(
    "/visibility",
    summary="Update wishlist visibility",
    security=SECURITY,
    responses={200: VisibilityResponse, 400: ErrorsResponse, 401: ErrorResponse},
)
def update_visibility(body: VisibilityBody):
    """Toggle the current user's wishlist between public and private."""
    user = _get_current_user()
    if not user:
        return jsonify({"error": "Not authenticated"}), 401

    user.wishlist_public = body.public
    db.session.commit()

    return jsonify(
        {
            "message": "Visibility updated",
            "wishlist_public": user.wishlist_public,
        }
    )


@wishlist_bp.get(
    "/user/<string:username>",
    summary="Get public wishlist",
    responses={
        200: PublicWishlistResponse,
        403: ErrorResponse,
        404: ErrorResponse,
    },
)
def get_user_wishlist(path: UsernamePath):
    """Get another user's wishlist (only if they made it public)."""
    target_user = db.session.execute(
        select(User).where(User.username == path.username)
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
            "items": [_item_dict(item, include_created=True) for item in items],
        }
    )


@wishlist_bp.get(
    "/game/<string:cheapshark_id>",
    summary="Get game details and deals",
    responses={200: GameDetailsResponse, 404: ErrorResponse},
)
def get_game_details(path: GamePath):
    """Get game details with the cheapest deals from the CheapShark API."""
    details = _get_game_details(path.cheapshark_id)

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
        except ValueError, TypeError:
            continue

    cheapest_ever = None
    ever_data = details.get("cheapestPriceEver")
    if ever_data:
        cheapest_ever = {
            "price": ever_data.get("price", "0"),
            "date": ever_data.get("date"),
        }

    return jsonify(
        {
            "info": details.get("info"),
            "cheapestActiveDeal": cheapest_active,
            "cheapestPriceEver": cheapest_ever,
        }
    )
