from datetime import UTC, datetime

from sqlalchemy.orm import Mapped, mapped_column

from models import Base


class WishlistItem(Base):
    __tablename__ = "wishlist_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(nullable=False)
    cheapshark_id: Mapped[str] = mapped_column(nullable=False)
    title: Mapped[str] = mapped_column(nullable=False)
    thumb: Mapped[str] = mapped_column(default="")
    notes: Mapped[str] = mapped_column(default="")
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC))
