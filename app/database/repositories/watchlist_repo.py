"""Repositories for Watchlists, Alerts, and Documents."""

from datetime import datetime
import json
from typing import List, Optional
from uuid import UUID
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.watchlist import Watchlist, Alert
from app.models.document import Document, DocumentChunk


class WatchlistRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add_ticker(self, user_id: UUID, ticker: str, company_name: Optional[str] = None) -> Watchlist:
        ticker_upper = ticker.upper()
        item = Watchlist(user_id=user_id, ticker=ticker_upper, company_name=company_name)
        self.session.add(item)
        await self.session.flush()
        return item

    async def get_by_ticker(self, user_id: UUID, ticker: str) -> Optional[Watchlist]:
        stmt = select(Watchlist).where(Watchlist.user_id == user_id, Watchlist.ticker == ticker.upper())
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def remove_ticker(self, user_id: UUID, ticker: str) -> bool:
        item = await self.get_by_ticker(user_id, ticker)
        if not item:
            return False
        await self.session.delete(item)
        await self.session.flush()
        return True

    async def add_or_update_ticker(self, user_id: UUID, ticker: str, company_name: Optional[str] = None) -> Watchlist:
        existing = await self.get_by_ticker(user_id, ticker)
        if existing:
            if company_name:
                existing.company_name = company_name
            await self.session.flush()
            return existing
        return await self.add_ticker(user_id=user_id, ticker=ticker, company_name=company_name)

    async def get_user_watchlist(self, user_id: UUID) -> List[Watchlist]:
        stmt = select(Watchlist).where(Watchlist.user_id == user_id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def clear_user_watchlist(self, user_id: UUID) -> int:
        items = await self.get_user_watchlist(user_id)
        for item in items:
            await self.session.delete(item)
        await self.session.flush()
        return len(items)


class AlertRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, user_id: UUID, alert_id: UUID) -> Optional[Alert]:
        stmt = select(Alert).where(Alert.user_id == user_id, Alert.id == alert_id)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def find_duplicate(
        self,
        user_id: UUID,
        alert_type: str,
        ticker: Optional[str] = None,
        condition: Optional[str] = None,
        threshold: Optional[float] = None,
        reminder_minutes: Optional[int] = None,
        scope: Optional[str] = None,
        title: Optional[str] = None,
    ) -> Optional[Alert]:
        stmt = select(Alert).where(
            Alert.user_id == user_id,
            Alert.alert_type == alert_type,
            Alert.is_active.is_(True),
        )
        if ticker is not None:
            stmt = stmt.where(Alert.ticker == ticker.upper())
        if condition is not None:
            stmt = stmt.where(Alert.condition == condition)
        if threshold is not None:
            stmt = stmt.where(Alert.threshold == threshold)
        if reminder_minutes is not None:
            stmt = stmt.where(Alert.reminder_minutes == reminder_minutes)
        if scope is not None:
            stmt = stmt.where(Alert.scope == scope)
        if title is not None:
            stmt = stmt.where(Alert.title == title)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def create_alert(
        self,
        user_id: UUID,
        ticker: Optional[str] = None,
        condition: Optional[str] = None,
        threshold: Optional[float] = None,
        alert_type: str = "price_threshold",
        operator: Optional[str] = None,
        reminder_minutes: Optional[int] = None,
        scope: Optional[str] = None,
        title: Optional[str] = None,
        details: Optional[str] = None,
        reminder_at_utc: Optional[datetime] = None,
        event_at_utc: Optional[datetime] = None,
    ) -> Alert:
        scope_value = scope or ("watchlist" if alert_type == "major_news" and not ticker else "ticker")
        alert = Alert(
            user_id=user_id,
            ticker=ticker.upper() if ticker else None,
            alert_type=alert_type,
            condition=condition,
            operator=operator,
            threshold=threshold,
            reminder_minutes=reminder_minutes,
            scope=scope_value,
            title=title,
            details=details,
            reminder_at_utc=reminder_at_utc,
            event_at_utc=event_at_utc,
            triggered=False,
            is_active=True,
        )
        self.session.add(alert)
        await self.session.flush()
        return alert

    async def get_active_alerts(self) -> List[Alert]:
        stmt = select(Alert).where(Alert.triggered.is_(False), Alert.is_active.is_(True))
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_user_alerts(self, user_id: UUID) -> List[Alert]:
        stmt = select(Alert).where(Alert.user_id == user_id).order_by(Alert.created_at.desc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_user_active_alerts(self, user_id: UUID) -> List[Alert]:
        stmt = select(Alert).where(Alert.user_id == user_id, Alert.is_active.is_(True)).order_by(Alert.created_at.desc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def cancel_alert(self, user_id: UUID, alert_id: UUID) -> bool:
        alert = await self.get_by_id(user_id, alert_id)
        if not alert:
            return False
        alert.is_active = False
        await self.session.flush()
        return True

    async def cancel_all(self, user_id: UUID) -> int:
        stmt = update(Alert).where(Alert.user_id == user_id, Alert.is_active.is_(True)).values(is_active=False)
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.rowcount or 0

    async def cancel_by_ticker(self, user_id: UUID, ticker: str) -> int:
        stmt = update(Alert).where(Alert.user_id == user_id, Alert.ticker == ticker.upper(), Alert.is_active.is_(True)).values(is_active=False)
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.rowcount or 0

    async def to_public_dict(self, alert: Alert) -> dict:
        return {
            "id": str(alert.id),
            "user_id": str(alert.user_id),
            "ticker": alert.ticker,
            "alert_type": alert.alert_type,
            "condition": alert.condition,
            "operator": alert.operator,
            "threshold": alert.threshold,
            "reminder_minutes": alert.reminder_minutes,
            "scope": alert.scope,
            "title": alert.title,
            "details": alert.details,
            "triggered": alert.triggered,
            "is_active": alert.is_active,
            "last_checked": alert.last_checked.isoformat() if alert.last_checked else None,
            "last_notified_at": alert.last_notified_at.isoformat() if alert.last_notified_at else None,
            "triggered_at": alert.triggered_at.isoformat() if alert.triggered_at else None,
            "reminder_at_utc": alert.reminder_at_utc.isoformat() if alert.reminder_at_utc else None,
            "event_at_utc": alert.event_at_utc.isoformat() if alert.event_at_utc else None,
            "created_at": alert.created_at.isoformat() if alert.created_at else None,
        }


class DocumentRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_document(
        self,
        user_id: UUID,
        filename: str,
        file_type: str,
        telegram_file_id: Optional[str] = None,
        content_type: Optional[str] = None,
        size_bytes: Optional[int] = None,
        status: str = "uploaded",
    ) -> Document:
        doc = Document(
            user_id=user_id,
            filename=filename,
            file_type=file_type,
            telegram_file_id=telegram_file_id,
            content_type=content_type,
            size_bytes=size_bytes,
            status=status,
        )
        self.session.add(doc)
        await self.session.flush()
        return doc

    async def get_by_id(self, document_id: UUID) -> Optional[Document]:
        stmt = select(Document).where(Document.id == document_id)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_user_documents(self, user_id: UUID, status: Optional[str] = None, limit: int = 10) -> List[Document]:
        stmt = select(Document).where(Document.user_id == user_id)
        if status:
            stmt = stmt.where(Document.status == status)
        stmt = stmt.order_by(Document.created_at.desc()).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_latest_ready_documents(self, user_id: UUID, limit: int = 2) -> List[Document]:
        return await self.get_user_documents(user_id=user_id, status="ready", limit=limit)

    async def get_latest_ready_document(self, user_id: UUID) -> Optional[Document]:
        docs = await self.get_latest_ready_documents(user_id=user_id, limit=1)
        return docs[0] if docs else None

    async def update_document(self, document_id: UUID, **fields) -> Optional[Document]:
        doc = await self.get_by_id(document_id)
        if not doc:
            return None
        for key, value in fields.items():
            if hasattr(doc, key) and value is not None:
                setattr(doc, key, value)
        if "status" in fields and fields["status"] is not None:
            doc.status = fields["status"]
        if fields.get("status") in {"ready", "failed"}:
            doc.processed_at = fields.get("processed_at") or datetime.utcnow()
        await self.session.flush()
        return doc

    async def mark_failed(self, document_id: UUID, error_message: str) -> Optional[Document]:
        return await self.update_document(
            document_id,
            status="failed",
            extraction_error=error_message,
            processed_at=datetime.utcnow(),
        )

    async def mark_ready(self, document_id: UUID, page_count: Optional[int] = None) -> Optional[Document]:
        return await self.update_document(
            document_id,
            status="ready",
            page_count=page_count,
            extraction_error=None,
            processed_at=datetime.utcnow(),
        )

    async def mark_processing(self, document_id: UUID) -> Optional[Document]:
        return await self.update_document(document_id, status="processing")

    async def add_chunks(self, document_id: UUID, chunks: List[dict]) -> None:
        for item in chunks:
            chunk = DocumentChunk(
                document_id=document_id,
                page_number=item.get("page_number"),
                chunk_index=item["chunk_index"],
                content=item["content"],
                embedding=item.get("embedding"),
            )
            self.session.add(chunk)
        await self.session.flush()

    async def get_document_chunks(self, document_id: UUID) -> List[DocumentChunk]:
        stmt = select(DocumentChunk).where(DocumentChunk.document_id == document_id).order_by(DocumentChunk.chunk_index.asc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def search_chunks(
        self,
        user_id: UUID,
        query_vector: List[float],
        limit: int = 4,
        document_ids: Optional[List[UUID]] = None,
    ) -> List[DocumentChunk]:
        stmt = select(DocumentChunk).join(Document).where(Document.user_id == user_id)
        if document_ids:
            stmt = stmt.where(Document.id.in_(document_ids))
        stmt = stmt.order_by(DocumentChunk.embedding.cosine_distance(query_vector)).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
