"""Aggregate API routes."""

from fastapi import APIRouter

from app.api.alerts import router as alerts_router
from app.api.users import router as users_router

api_router = APIRouter()
api_router.include_router(users_router, prefix="/users", tags=["users"])
api_router.include_router(alerts_router, prefix="/alerts", tags=["alerts"])
