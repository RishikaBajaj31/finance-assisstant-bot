"""Pydantic schemas for Conversations and Memory."""

from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict


class MessageRequest(BaseModel):
    telegram_id: int
    content: str
    username: Optional[str] = None
    full_name: Optional[str] = None


class MessageResponse(BaseModel):
    role: str
    content: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MemoryResponse(BaseModel):
    id: UUID
    content: str
    memory_type: str
    importance: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
