"""Pydantic schemas for Watchlist and Alerts."""

from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict


class WatchlistCreate(BaseModel):
    ticker: str
    company_name: Optional[str] = None
    notes: Optional[str] = None


class WatchlistResponse(WatchlistCreate):
    id: UUID
    user_id: UUID
    added_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AlertCreate(BaseModel):
    ticker: Optional[str] = None
    alert_type: str = "price_threshold"
    condition: Optional[str] = None
    operator: Optional[str] = None
    threshold: Optional[float] = None
    reminder_minutes: Optional[int] = None
    scope: Optional[str] = None
    title: Optional[str] = None
    details: Optional[str] = None


class AlertResponse(AlertCreate):
    id: UUID
    user_id: UUID
    triggered: bool
    is_active: bool
    last_checked: Optional[datetime] = None
    last_notified_at: Optional[datetime] = None
    triggered_at: Optional[datetime] = None
    reminder_at_utc: Optional[datetime] = None
    event_at_utc: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
