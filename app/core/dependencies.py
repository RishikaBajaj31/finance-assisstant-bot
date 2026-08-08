"""FastAPI dependency providers."""

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from app.database.connection import get_db_session
from app.services.alert_service import AlertService
from app.services.briefing_service import BriefingService
from app.services.document_service import DocumentService
from app.services.memory_service import MemoryService
from app.services.news_service import news_service
from app.services.research_service import research_service
from app.services.user_service import UserService


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async for session in get_db_session():
        yield session


def get_user_service(session: AsyncSession) -> UserService:
    return UserService(session)


def get_memory_service(session: AsyncSession) -> MemoryService:
    return MemoryService(session)


def get_briefing_service(session: AsyncSession) -> BriefingService:
    return BriefingService(session)


def get_alert_service(session: AsyncSession) -> AlertService:
    return AlertService(session)


def get_document_service(session: AsyncSession) -> DocumentService:
    return DocumentService(session)


__all__ = [
    "get_session",
    "get_user_service",
    "get_memory_service",
    "get_briefing_service",
    "get_alert_service",
    "get_document_service",
    "research_service",
    "news_service",
]
