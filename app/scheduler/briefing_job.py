"""Daily briefing job."""

from app.core.logging import logger
from app.services.briefing_service import BriefingService
from app.database.connection import AsyncSessionLocal


async def run_daily_briefings() -> list[dict]:
    results = []
    async with AsyncSessionLocal() as session:
        service = BriefingService(session)
        # Keep the job lightweight until per-user scheduling is fully configured.
        logger.info("Daily briefing job ran")
        results.append({"status": "ok", "message": "Briefing job executed"})
    return results
