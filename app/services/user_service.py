"""User profile management service."""

from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.repositories.user_repo import UserRepository
from app.models.user import User


class UserService:
    def __init__(self, session: AsyncSession):
        self.repo = UserRepository(session)

    async def get_or_create_user(self, telegram_id: int, username: Optional[str] = None, full_name: Optional[str] = None) -> User:
        """Fetch user by Telegram ID or create new user entry."""
        user = await self.repo.get_by_telegram_id(telegram_id)
        if not user:
            user = await self.repo.create_user(telegram_id, username, full_name)
        return user

    async def update_profile(self, telegram_id: int, role: str, sectors: list, interests: list, briefing_time: str = "08:00") -> User:
        """Update onboarding profile details."""
        user = await self.get_or_create_user(telegram_id)
        return await self.repo.update_onboarding(user.id, role, sectors, interests, briefing_time)
