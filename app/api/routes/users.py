"""User API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import UserCreateRequest, UserResponse
from app.core.database import get_session
from app.services.users import create_or_update_user, get_user_by_telegram

router = APIRouter(prefix="/users", tags=["users"])


@router.post("", response_model=UserResponse)
async def create_user(
    payload: UserCreateRequest,
    session: AsyncSession = Depends(get_session),
) -> UserResponse:
    user = await create_or_update_user(session, **payload.model_dump())
    return UserResponse.model_validate(user)


@router.get("/{telegram_id}", response_model=UserResponse)
async def get_user(
    telegram_id: int,
    session: AsyncSession = Depends(get_session),
) -> UserResponse:
    user = await get_user_by_telegram(session, telegram_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return UserResponse.model_validate(user)
