"""Pydantic schemas for User and UserPreferences."""

from datetime import datetime
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict


class UserPreferenceBase(BaseModel):
    sectors: List[str] = []
    interests: List[str] = []
    risk_tolerance: str = "moderate"
    investment_style: str = "growth"


class UserPreferenceCreate(UserPreferenceBase):
    pass


class UserPreferenceResponse(UserPreferenceBase):
    id: UUID
    user_id: UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserBase(BaseModel):
    telegram_id: int
    username: Optional[str] = None
    full_name: Optional[str] = None
    role: Optional[str] = None
    briefing_time: str = "08:00"
    timezone: str = "UTC"


class UserCreate(UserBase):
    pass


class UserOnboardingUpdate(BaseModel):
    role: str
    sectors: List[str] = []
    interests: List[str] = []
    briefing_time: str = "08:00"


class UserResponse(UserBase):
    id: UUID
    onboarding_complete: bool
    created_at: datetime
    preferences: Optional[UserPreferenceResponse] = None

    model_config = ConfigDict(from_attributes=True)
