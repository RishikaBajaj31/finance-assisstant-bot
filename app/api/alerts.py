"""Alert endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_session
from app.database.repositories.watchlist_repo import AlertRepository
from app.schemas.alert import AlertCreate, AlertResponse

router = APIRouter()


@router.post("/{user_id}", response_model=AlertResponse)
async def create_alert(user_id: UUID, payload: AlertCreate, session: AsyncSession = Depends(get_session)):
    alert = await AlertRepository(session).create_alert(user_id=user_id, **payload.model_dump(exclude_none=True))
    return alert


@router.get("/{user_id}", response_model=list[AlertResponse])
async def list_alerts(user_id: UUID, session: AsyncSession = Depends(get_session)):
    alerts = await AlertRepository(session).get_user_alerts(user_id)
    return alerts


@router.delete("/{user_id}/{alert_id}")
async def cancel_alert(user_id: UUID, alert_id: UUID, session: AsyncSession = Depends(get_session)):
    cancelled = await AlertRepository(session).cancel_alert(user_id, alert_id)
    if not cancelled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")
    return {"ok": True}


@router.delete("/{user_id}")
async def cancel_all_alerts(user_id: UUID, session: AsyncSession = Depends(get_session)):
    cancelled = await AlertRepository(session).cancel_all(user_id)
    return {"ok": True, "cancelled": cancelled}
