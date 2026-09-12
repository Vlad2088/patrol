"""Дашборд диспетчера: сводка по объектам за дату."""
from datetime import date as date_cls, datetime, time, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select

from app.core.deps import CurrentUser, require_dispatcher
from app.db import get_db
from app.models import Object, Patrol, PatrolStatus, Violation
from app.schemas import DashboardOut, DashboardRow, ViolationOut

router = APIRouter()


def _parse_date(date: str | None) -> date_cls:
    if date is None:
        return datetime.utcnow().date()
    try:
        return date_cls.fromisoformat(date)
    except ValueError:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail="date: ГГГГ-ММ-ДД")


@router.get("/dashboard", response_model=DashboardOut)
def dashboard(
    date: str | None = None,
    db=Depends(get_db),
    user: CurrentUser = Depends(require_dispatcher),
) -> DashboardOut:
    d = _parse_date(date)
    rows = []
    objects = list(db.scalars(select(Object).where(Object.is_active.is_(True)).order_by(Object.name)))
    for obj in objects:
        patrols = list(
            db.scalars(
                select(Patrol).where(Patrol.object_id == obj.id, Patrol.patrol_date == d)
            )
        )
        if not patrols:
            rows.append(DashboardRow(object_id=obj.id, object_name=obj.name,
                                     patrols_total=0, in_progress=0, completed=0,
                                     missed=0, partial=0, planned=0, violations=0))
            continue
        counts = {"in_progress": 0, "completed": 0, "missed": 0, "partial": 0, "planned": 0}
        for p in patrols:
            counts[p.status.value] = counts.get(p.status.value, 0) + 1
        violations = db.scalar(
            select(func.count()).select_from(Violation).where(
                Violation.patrol_id.in_([p.id for p in patrols])
            )
        ) or 0
        rows.append(DashboardRow(
            object_id=obj.id, object_name=obj.name,
            patrols_total=len(patrols),
            in_progress=counts["in_progress"], completed=counts["completed"],
            missed=counts["missed"], partial=counts["partial"],
            planned=counts["planned"], violations=violations,
        ))
    return DashboardOut(date=d, rows=rows)


@router.get("/notifications", response_model=list[ViolationOut])
def notifications(
    from_: str | None = None,
    to: str | None = None,
    unread_only: bool = False,
    db=Depends(get_db),
    user: CurrentUser = Depends(require_dispatcher),
):
    """Нарушения за период = уведомления кабинета."""
    q = select(Violation).order_by(Violation.detected_at.desc()).limit(200)
    violations = list(db.scalars(q))
    return [
        ViolationOut(
            id=v.id, patrol_id=v.patrol_id, kind=v.kind, details=v.details,
            detected_at=v.detected_at,
        )
        for v in violations
    ]
