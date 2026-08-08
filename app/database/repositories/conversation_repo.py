"""Repository for Conversation history database operations."""

from typing import List
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.conversation import Conversation


class ConversationRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add_message(self, user_id: UUID, role: str, content: str) -> Conversation:
        """Add a conversation message turn."""
        message = Conversation(user_id=user_id, role=role, content=content)
        self.session.add(message)
        await self.session.flush()
        return message

    async def get_recent_history(self, user_id: UUID, limit: int = 10) -> List[Conversation]:
        """Fetch latest conversation turns ordered chronologically."""
        stmt = (
            select(Conversation)
            .where(Conversation.user_id == user_id)
            .order_by(Conversation.created_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        messages = list(result.scalars().all())
        return list(reversed(messages))
