"""Forecast ORM model."""

from __future__ import annotations

import enum
import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ForecastKind(str, enum.Enum):
    SHORT = "short"
    FULL = "full"


class Forecast(Base):
    """Stored forecasts (short/full) per user per day."""

    __tablename__ = "forecasts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[ForecastKind] = mapped_column(
        Enum(ForecastKind, name="forecast_kind"), index=True
    )
    content: Mapped[str] = mapped_column(Text)
    forecast_date: Mapped[date] = mapped_column(Date, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )
    speed_level: Mapped[int | None] = mapped_column(nullable=True)
    depth_level: Mapped[int | None] = mapped_column(nullable=True)
    caution_level: Mapped[int | None] = mapped_column(nullable=True)

    user = relationship("User", backref="forecasts")

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return (
            f"<Forecast id={self.id} user_id={self.user_id} "
            f"kind={self.kind} date={self.forecast_date}>"
        )
