import asyncio
import os

from sqlalchemy import text

os.environ.setdefault("ENABLE_SCHEDULER", "false")
os.environ.setdefault("GEMINI_API_KEY", "mock-key")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "mock-token")
os.environ.setdefault("NEWS_API_KEY", "")

from app.database.connection import AsyncSessionLocal, Base, engine
from app.database.migrations.ensure_schema import ensure_schema
import app.models  # noqa: F401


TABLES = [
    "document_chunks",
    "documents",
    "research_history",
    "alerts",
    "watchlists",
    "telegram_updates",
    "memories",
    "conversations",
    "user_preferences",
    "users",
]


async def prepare_db():
    await ensure_schema(engine)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(text(f"TRUNCATE TABLE {', '.join(TABLES)} RESTART IDENTITY CASCADE"))
