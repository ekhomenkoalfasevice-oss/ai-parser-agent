"""Pydantic schemas for API requests/responses."""

from .user import UserCreateRequest, UserResponse
from .forecast import ShortForecastRequest, ShortForecastResponse

__all__ = [
    "UserCreateRequest",
    "UserResponse",
    "ShortForecastRequest",
    "ShortForecastResponse",
]
