"""API router registration."""

from fastapi import APIRouter

from .users import router as users_router
from .forecasts import router as forecasts_router

api_router = APIRouter()
api_router.include_router(users_router)
api_router.include_router(forecasts_router)

__all__ = ["api_router"]
