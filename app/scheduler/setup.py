"""APScheduler configuration."""

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import settings
from app.scheduler.alert_job import run_alert_checks
from app.scheduler.briefing_job import run_daily_briefings


def create_scheduler() -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone="UTC")
    if settings.ENABLE_SCHEDULER:
        scheduler.add_job(run_daily_briefings, "cron", hour=8, minute=0, id="daily_briefings", replace_existing=True)
        scheduler.add_job(run_alert_checks, "interval", minutes=15, id="alert_checks", replace_existing=True)
    return scheduler
