"""Watchlist and Alert ORM models."""

import uuid
from datetime import datetime
from sqlalchemy import BigInteger, Boolean, Column, DateTime, Float, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database.connection import Base


class Watchlist(Base):
    __tablename__ = "watchlists"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    ticker = Column(String(20), nullable=False)
    company_name = Column(String(150), nullable=True)
    added_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    notes = Column(Text, nullable=True)

    __table_args__ = (UniqueConstraint("user_id", "ticker", name="unique_user_ticker"),)
    user = relationship("User", back_populates="watchlists")


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    ticker = Column(String(20), nullable=True, index=True)
    alert_type = Column(String(40), nullable=False, default="price_threshold")
    condition = Column(String(50), nullable=True)
    operator = Column(String(12), nullable=True)
    threshold = Column(Float, nullable=True)
    reminder_minutes = Column(BigInteger, nullable=True)
    scope = Column(String(30), nullable=False, default="ticker")
    title = Column(String(255), nullable=True)
    details = Column(Text, nullable=True)
    triggered = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    last_checked = Column(DateTime(timezone=True), nullable=True)
    last_notified_at = Column(DateTime(timezone=True), nullable=True)
    triggered_at = Column(DateTime(timezone=True), nullable=True)
    reminder_at_utc = Column(DateTime(timezone=True), nullable=True)
    event_at_utc = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    user = relationship("User", back_populates="alerts")
