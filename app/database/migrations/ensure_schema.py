"""Lightweight schema compatibility checks for evolving tables."""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.database.connection import Base


async def ensure_schema(engine: AsyncEngine) -> None:
    """Create tables first, then apply idempotent compatibility updates."""

    # Import model modules so SQLAlchemy has every table registered before create_all().
    import app.models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(text("ALTER TABLE IF EXISTS memories ADD COLUMN IF NOT EXISTS memory_key VARCHAR(120)"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_memories_user_memory_key ON memories (user_id, memory_key)"))
        await conn.execute(text("ALTER TABLE IF EXISTS documents ADD COLUMN IF NOT EXISTS telegram_file_id VARCHAR(255)"))
        await conn.execute(text("ALTER TABLE IF EXISTS documents ADD COLUMN IF NOT EXISTS content_type VARCHAR(100)"))
        await conn.execute(text("ALTER TABLE IF EXISTS documents ADD COLUMN IF NOT EXISTS size_bytes BIGINT"))
        await conn.execute(text("ALTER TABLE IF EXISTS documents ADD COLUMN IF NOT EXISTS page_count INT"))
        await conn.execute(text("ALTER TABLE IF EXISTS documents ADD COLUMN IF NOT EXISTS extraction_error TEXT"))
        await conn.execute(text("ALTER TABLE IF EXISTS documents ADD COLUMN IF NOT EXISTS processed_at TIMESTAMP WITH TIME ZONE"))
        await conn.execute(text("ALTER TABLE IF EXISTS documents ALTER COLUMN status SET DEFAULT 'uploaded'"))
        await conn.execute(text("ALTER TABLE IF EXISTS document_chunks ADD COLUMN IF NOT EXISTS page_number INT"))
        await conn.execute(text("ALTER TABLE IF EXISTS alerts ADD COLUMN IF NOT EXISTS alert_type VARCHAR(40)"))
        await conn.execute(text("ALTER TABLE IF EXISTS alerts ADD COLUMN IF NOT EXISTS operator VARCHAR(12)"))
        await conn.execute(text("ALTER TABLE IF EXISTS alerts ADD COLUMN IF NOT EXISTS reminder_minutes BIGINT"))
        await conn.execute(text("ALTER TABLE IF EXISTS alerts ADD COLUMN IF NOT EXISTS scope VARCHAR(30)"))
        await conn.execute(text("ALTER TABLE IF EXISTS alerts ADD COLUMN IF NOT EXISTS title VARCHAR(255)"))
        await conn.execute(text("ALTER TABLE IF EXISTS alerts ADD COLUMN IF NOT EXISTS details TEXT"))
        await conn.execute(text("ALTER TABLE IF EXISTS alerts ADD COLUMN IF NOT EXISTS is_active BOOLEAN"))
        await conn.execute(text("ALTER TABLE IF EXISTS alerts ADD COLUMN IF NOT EXISTS last_notified_at TIMESTAMP WITH TIME ZONE"))
        await conn.execute(text("ALTER TABLE IF EXISTS alerts ADD COLUMN IF NOT EXISTS triggered_at TIMESTAMP WITH TIME ZONE"))
        await conn.execute(text("ALTER TABLE IF EXISTS alerts ADD COLUMN IF NOT EXISTS reminder_at_utc TIMESTAMP WITH TIME ZONE"))
        await conn.execute(text("ALTER TABLE IF EXISTS alerts ADD COLUMN IF NOT EXISTS event_at_utc TIMESTAMP WITH TIME ZONE"))
        await conn.execute(text("ALTER TABLE IF EXISTS alerts ALTER COLUMN alert_type SET DEFAULT 'price_threshold'"))
        await conn.execute(text("ALTER TABLE IF EXISTS alerts ALTER COLUMN scope SET DEFAULT 'ticker'"))
        await conn.execute(text("ALTER TABLE IF EXISTS alerts ALTER COLUMN ticker DROP NOT NULL"))
        await conn.execute(text("ALTER TABLE IF EXISTS alerts ALTER COLUMN condition DROP NOT NULL"))
        await conn.execute(text("ALTER TABLE IF EXISTS alerts ALTER COLUMN threshold DROP NOT NULL"))
        await conn.execute(text("ALTER TABLE IF EXISTS alerts ALTER COLUMN triggered SET DEFAULT FALSE"))
        await conn.execute(text("ALTER TABLE IF EXISTS alerts ALTER COLUMN is_active SET DEFAULT TRUE"))
