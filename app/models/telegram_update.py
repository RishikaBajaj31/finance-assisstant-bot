"""Telegram update deduplication ORM model."""

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Column, DateTime
from sqlalchemy.dialects.postgresql import UUID

from app.database.connection import Base


class TelegramUpdate(Base):
    __tablename__ = "telegram_updates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    update_id = Column(BigInteger, unique=True, nullable=False, index=True)
    processed_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
