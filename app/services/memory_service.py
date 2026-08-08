"""Service for long-term vector search and conversation memory."""

import json
from dataclasses import dataclass
from typing import List, Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.repositories.conversation_repo import ConversationRepository
from app.database.repositories.memory_repo import MemoryRepository
from app.integrations.gemini import gemini_client
from app.models.memory import Memory
from app.prompts.memory import MEMORY_EXTRACTION_SYSTEM_PROMPT


@dataclass
class MemoryExtraction:
    should_remember: bool
    memory_type: str
    content: Optional[str]
    importance: float
    memory_key: Optional[str] = None


class MemoryService:
    def __init__(self, session: AsyncSession):
        self.conv_repo = ConversationRepository(session)
        self.mem_repo = MemoryRepository(session)

    async def record_user_message(self, user_id: UUID, content: str):
        """Save user message turn."""
        await self.conv_repo.add_message(user_id=user_id, role="user", content=content)

    async def record_assistant_message(self, user_id: UUID, content: str):
        """Save assistant response turn."""
        await self.conv_repo.add_message(user_id=user_id, role="assistant", content=content)

    async def add_semantic_memory(self, user_id: UUID, fact: str, memory_type: str = "user_fact") -> Memory:
        """Embed and persist long-term semantic memory in pgvector."""
        embedding = await gemini_client.generate_embedding(fact)
        return await self.mem_repo.upsert_memory(
            user_id=user_id,
            content=fact,
            memory_type=memory_type,
            embedding=embedding,
            importance=3,
        )

    async def maybe_store_memory(
        self,
        user_id: UUID,
        user_message: str,
        assistant_message: str = "",
        conversation_history: str = "",
        recalled_memories: Optional[List[str]] = None,
    ) -> Optional[Memory]:
        """Extract a durable fact from the conversation and persist it if useful."""
        recalled_memories = recalled_memories or []
        parsed = await gemini_client.generate_json(
            prompt=(
                "Evaluate whether the following user message contains a durable preference or profile fact.\n"
                f"Conversation history:\n{json.dumps(conversation_history, ensure_ascii=True)}\n\n"
                f"Relevant memories:\n{json.dumps(recalled_memories, ensure_ascii=True)}\n\n"
                f"Latest user message:\n{json.dumps(user_message, ensure_ascii=True)}\n\n"
                f"Assistant reply:\n{json.dumps(assistant_message, ensure_ascii=True)}"
            ),
            system_instruction=MEMORY_EXTRACTION_SYSTEM_PROMPT,
            default={},
        )
        if not parsed:
            lowered = user_message.lower()
            if any(phrase in lowered for phrase in ("i am", "i follow", "i care about", "i prefer", "i usually", "i mainly")):
                content = user_message.strip()
                return await self.add_semantic_memory(user_id, content)
            return None

        extraction = MemoryExtraction(
            should_remember=bool(parsed.get("should_remember")),
            memory_type=str(parsed.get("memory_type") or "preference"),
            content=parsed.get("content") or None,
            importance=float(parsed.get("importance") or 0.5),
            memory_key=parsed.get("memory_key") or None,
        )
        if not extraction.should_remember or not extraction.content:
            return None

        embedding = await gemini_client.generate_embedding(extraction.content)
        return await self.mem_repo.upsert_memory(
            user_id=user_id,
            content=extraction.content,
            memory_type=extraction.memory_type,
            embedding=embedding,
            memory_key=extraction.memory_key,
            importance=max(1, min(10, int(round(extraction.importance * 10)))),
        )

    async def recall_relevant_memories(self, user_id: UUID, query: str, limit: int = 4) -> List[str]:
        """Search top-K relevant memories using vector similarity."""
        query_vector = await gemini_client.generate_embedding(query)
        memories = await self.mem_repo.search_similar(user_id=user_id, query_vector=query_vector, limit=limit)
        if not memories:
            all_mems = await self.mem_repo.get_all_memories(user_id)
            return [m.content for m in all_mems[:limit]]
        return [m.content for m in memories]

    async def get_conversation_history(self, user_id: UUID, limit: int = 6) -> str:
        """Format recent turn history as prompt string."""
        turns = await self.conv_repo.get_recent_history(user_id=user_id, limit=limit)
        return "\n".join([f"{t.role.capitalize()}: {t.content}" for t in turns])
