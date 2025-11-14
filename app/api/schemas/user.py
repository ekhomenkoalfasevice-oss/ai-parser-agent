"""User API schemas."""

from __future__ import annotations

from datetime import date, time
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class UserCreateRequest(BaseModel):
    telegram_id: int = Field(..., ge=1)
    first_name: Optional[str] = Field(None, max_length=128)
    last_name: Optional[str] = Field(None, max_length=128)
    username: Optional[str] = Field(None, max_length=64)
    language: Optional[str] = Field(None, max_length=8)
    birth_date: Optional[date] = None
    birth_time: Optional[time] = None
    birth_city: Optional[str] = Field(None, max_length=128)
    timezone: Optional[str] = Field(default="UTC", max_length=64)


class UserResponse(BaseModel):
    id: UUID
    telegram_id: int
    birth_date: Optional[date]
    birth_time: Optional[time]
    birth_city: Optional[str]
    timezone: str

    class Config:
        from_attributes = True
