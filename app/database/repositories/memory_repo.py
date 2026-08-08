"""Repository for Long-Term Semantic Memory with pgvector."""

from typing import List, Optional
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.memory import Memory


class MemoryRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add_memory(
        self,
        user_id: UUID,
        content: str,
        memory_type: str = "user_fact",
        embedding: Optional[List[float]] = None,
        memory_key: Optional[str] = None,
        importance: int = 3,
    ) -> Memory:
        """Store a long-term memory entry with optional vector embedding."""
        mem = Memory(
            user_id=user_id,
            content=content,
            memory_key=memory_key,
            memory_type=memory_type,
            importance=importance,
            embedding=embedding
        )
        self.session.add(mem)
        await self.session.flush()
        return mem

    async def get_by_key(self, user_id: UUID, memory_key: str) -> Optional[Memory]:
        stmt = select(Memory).where(Memory.user_id == user_id, Memory.memory_key == memory_key)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def find_duplicate(self, user_id: UUID, content: str) -> Optional[Memory]:
        normalized = " ".join(content.lower().split())
        stmt = select(Memory).where(Memory.user_id == user_id)
        result = await self.session.execute(stmt)
        for mem in result.scalars().all():
            if " ".join(mem.content.lower().split()) == normalized:
                return mem
        return None

    async def upsert_memory(
        self,
        user_id: UUID,
        content: str,
        memory_type: str = "user_fact",
        embedding: Optional[List[float]] = None,
        memory_key: Optional[str] = None,
        importance: int = 3,
    ) -> Memory:
        if memory_key:
            existing = await self.get_by_key(user_id, memory_key)
            if existing:
                existing.content = content
                existing.memory_type = memory_type
                existing.importance = importance
                existing.embedding = embedding
                await self.session.flush()
                return existing

        duplicate = await self.find_duplicate(user_id, content)
        if duplicate:
            duplicate.memory_type = memory_type
            duplicate.importance = max(duplicate.importance or 0, importance)
            duplicate.embedding = embedding or duplicate.embedding
            if memory_key:
                duplicate.memory_key = memory_key
            await self.session.flush()
            return duplicate

        return await self.add_memory(
            user_id=user_id,
            content=content,
            memory_type=memory_type,
            embedding=embedding,
            memory_key=memory_key,
            importance=importance,
        )

    async def search_similar(
        self, user_id: UUID, query_vector: List[float], limit: int = 5
    ) -> List[Memory]:
        """Perform pgvector cosine similarity search for memories."""
        stmt = (
            select(Memory)
            .where(Memory.user_id == user_id)
            .order_by(Memory.embedding.cosine_distance(query_vector))
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_all_memories(self, user_id: UUID) -> List[Memory]:
        """Retrieve all long-term memories for a user."""
        stmt = select(Memory).where(Memory.user_id == user_id).order_by(Memory.created_at.desc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
