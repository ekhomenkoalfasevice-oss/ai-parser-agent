"""Forecast API schemas."""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field


class ShortForecastRequest(BaseModel):
    telegram_id: int = Field(..., ge=1)


class ShortForecastResponse(BaseModel):
    text: str
    forecast_date: date
    generated_at: datetime
    speed_level: Optional[int]
    depth_level: Optional[int]
    caution_level: Optional[int]

    class Config:
        from_attributes = True
