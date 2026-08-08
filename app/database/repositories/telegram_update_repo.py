"""Repository for Telegram update idempotency tracking."""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert

from app.models.telegram_update import TelegramUpdate


class TelegramUpdateRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def claim_update(self, update_id: int) -> bool:
        """Claim a Telegram update_id so it is only processed once."""
        stmt = (
            insert(TelegramUpdate)
            .values(update_id=update_id)
            .on_conflict_do_nothing(index_elements=[TelegramUpdate.update_id])
            .returning(TelegramUpdate.id)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none() is not None
