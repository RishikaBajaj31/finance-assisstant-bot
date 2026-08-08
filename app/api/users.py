"""User endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_session
from app.schemas.user import UserResponse, UserOnboardingUpdate
from app.services.user_service import UserService

router = APIRouter()


@router.get("/{telegram_id}", response_model=UserResponse)
async def get_user(telegram_id: int, session: AsyncSession = Depends(get_session)):
    user = await UserService(session).get_or_create_user(telegram_id)
    return user


@router.post("/{telegram_id}/onboarding", response_model=UserResponse)
async def update_onboarding(
    telegram_id: int,
    payload: UserOnboardingUpdate,
    session: AsyncSession = Depends(get_session),
):
    user = await UserService(session).update_profile(
        telegram_id=telegram_id,
        role=payload.role,
        sectors=payload.sectors,
        interests=payload.interests,
        briefing_time=payload.briefing_time,
    )
    return user
