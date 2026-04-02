"""
api/notifications.py — Notifications endpoints.
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, desc, func, update
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from backend.database import get_db
from backend.models import Notification

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.get("")
async def list_notifications(
    is_read: Optional[bool] = Query(None),
    limit: int = Query(50),
    db: AsyncSession = Depends(get_db),
):
    q = select(Notification).order_by(desc(Notification.created_at)).limit(limit)
    if is_read is not None:
        q = q.where(Notification.is_read == is_read)
    result = await db.execute(q)
    notifications = result.scalars().all()
    unread_count = await db.scalar(
        select(func.count(Notification.id)).where(Notification.is_read == False)
    )
    return {
        "notifications": [
            {
                "id": n.id,
                "type": n.type,
                "title": n.title,
                "message": n.message,
                "job_id": n.job_id,
                "sent_at": n.sent_at.isoformat() if n.sent_at else None,
                "is_read": n.is_read,
                "created_at": n.created_at.isoformat() if n.created_at else None,
            }
            for n in notifications
        ],
        "unread_count": unread_count or 0,
    }


@router.patch("/{notif_id}/read")
async def mark_read(notif_id: int, db: AsyncSession = Depends(get_db)):
    await db.execute(
        update(Notification).where(Notification.id == notif_id).values(is_read=True)
    )
    return {"id": notif_id, "is_read": True}


@router.post("/mark-all-read")
async def mark_all_read(db: AsyncSession = Depends(get_db)):
    await db.execute(update(Notification).values(is_read=True))
    return {"message": "All notifications marked as read."}
