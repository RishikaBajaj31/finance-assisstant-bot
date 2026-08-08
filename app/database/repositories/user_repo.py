"""Repository for User database operations."""

from typing import Optional, Sequence
from uuid import UUID
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User, UserPreference


class UserRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_telegram_id(self, telegram_id: int) -> Optional[User]:
        """Fetch user by Telegram ID with preferences pre-loaded."""
        stmt = select(User).options(selectinload(User.preferences)).where(User.telegram_id == telegram_id)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_by_id(self, user_id: UUID) -> Optional[User]:
        """Fetch user by internal UUID."""
        stmt = select(User).options(selectinload(User.preferences)).where(User.id == user_id)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def create_user(self, telegram_id: int, username: Optional[str] = None, full_name: Optional[str] = None) -> User:
        """Create a new user with default preferences."""
        user = User(telegram_id=telegram_id, username=username, full_name=full_name)
        self.session.add(user)
        await self.session.flush()

        preference = UserPreference(user_id=user.id)
        self.session.add(preference)
        await self.session.flush()
        return user

    async def update_user_profile(
        self,
        user_id: UUID,
        role: Optional[str] = None,
        briefing_time: Optional[str] = None,
        timezone: Optional[str] = None,
        onboarding_complete: Optional[bool] = None,
    ) -> User:
        """Update top-level user fields without overwriting unknown values."""
        user = await self.get_by_id(user_id)
        if user:
            if role is not None:
                user.role = role
            if briefing_time is not None:
                user.briefing_time = briefing_time
            if timezone is not None:
                user.timezone = timezone
            if onboarding_complete is not None:
                user.onboarding_complete = onboarding_complete
            user.updated_at = datetime.utcnow()
            await self.session.flush()
        return user

    async def upsert_preferences(
        self,
        user_id: UUID,
        sectors: Optional[Sequence[str]] = None,
        interests: Optional[Sequence[str]] = None,
    ) -> UserPreference:
        """Upsert user preferences without wiping existing values."""
        pref_stmt = select(UserPreference).where(UserPreference.user_id == user_id)
        pref_res = await self.session.execute(pref_stmt)
        pref = pref_res.scalars().first()
        if not pref:
            pref = UserPreference(user_id=user_id)
            self.session.add(pref)

        if sectors:
            pref.sectors = list(dict.fromkeys([s for s in sectors if s]))
        if interests:
            pref.interests = list(dict.fromkeys([i for i in interests if i]))

        pref.updated_at = datetime.utcnow()
        await self.session.flush()
        return pref
