"""Forecast API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import ShortForecastRequest, ShortForecastResponse
from app.core.database import get_session
from app.services.forecasts import get_or_create_short_forecast
from app.services.users import get_user_by_telegram

router = APIRouter(prefix="/forecasts", tags=["forecasts"])


@router.post("/short", response_model=ShortForecastResponse)
async def short_forecast(
    payload: ShortForecastRequest,
    session: AsyncSession = Depends(get_session),
) -> ShortForecastResponse:
    user = await get_user_by_telegram(session, payload.telegram_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if not user.birth_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User profile incomplete",
        )
    forecast = await get_or_create_short_forecast(session, user)
    return ShortForecastResponse(
        text=forecast.content,
        forecast_date=forecast.forecast_date,
        generated_at=forecast.created_at,
        speed_level=forecast.speed_level,
        depth_level=forecast.depth_level,
        caution_level=forecast.caution_level,
    )
