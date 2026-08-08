"""FastAPI application entrypoint."""

from fastapi import FastAPI

from app.api.router import api_router
from app.api.webhook import router as webhook_router
from app.config import settings
from app.core.logging import logger
from app.database.connection import engine
from app.database.migrations.ensure_schema import ensure_schema
from app.scheduler.setup import create_scheduler


app = FastAPI(title=settings.PROJECT_NAME, version="0.1.0")
app.include_router(api_router, prefix=settings.API_V1_STR)
app.include_router(webhook_router)
scheduler = create_scheduler()


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.on_event("startup")
async def on_startup() -> None:
    logger.info("AI Financial Assistant starting up")
    await ensure_schema(engine)
    if settings.ENABLE_SCHEDULER:
        scheduler.start()


@app.on_event("shutdown")
async def on_shutdown() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
    await engine.dispose()
