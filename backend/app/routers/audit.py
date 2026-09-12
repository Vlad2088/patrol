"""Журнал аудита (только чтение)."""
from fastapi import APIRouter, Depends
from sqlalchemy import select

from app.core.deps import CurrentUser, require_dispatcher
from app.db import get_db
from app.models import AuditLog
from app.schemas import AuditOut

router = APIRouter()


@router.get("/audit", response_model=list[AuditOut])
def list_audit(
    user_id: int | None = None,
    from_: str | None = None,
    to: str | None = None,
    db=Depends(get_db),
    user: CurrentUser = Depends(require_dispatcher),
):
    from datetime import datetime

    q = select(AuditLog).order_by(AuditLog.created_at.desc())
    if user_id is not None:
        q = q.where(AuditLog.user_id == user_id)
    if from_:
        q = q.where(AuditLog.created_at >= datetime.fromisoformat(from_))
    if to:
        q = q.where(AuditLog.created_at <= datetime.fromisoformat(to))
    return list(db.scalars(q.limit(1000)))
