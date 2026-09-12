"""Мониторинг обходов (диспетчер)."""
from datetime import date as date_cls

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from app.core.deps import CurrentUser, require_dispatcher
from app.db import get_db
from app.models import Object, Patrol, Route
from app.schemas import PatrolOut

router = APIRouter()


def _patrol_out(p: Patrol) -> PatrolOut:
    return PatrolOut(
        id=p.id,
        object_id=p.object_id,
        object_name=p.object.name if p.object else "",
        route_id=p.route_id,
        route_name=p.route.name if p.route else "",
        patrol_date=p.patrol_date,
        window_start=p.window_start,
        window_end=p.window_end,
        status=p.status,
        started_by_id=p.started_by_id,
        started_at=p.started_at,
        finished_at=p.finished_at,
        checkpoints_total=p.checkpoints_total,
        checkpoints_scanned=p.checkpoints_scanned,
    )


@router.get("/patrols", response_model=list[PatrolOut])
def list_patrols(
    date: str | None = None,
    object_id: int | None = None,
    status_filter: str | None = None,
    db=Depends(get_db),
    user: CurrentUser = Depends(require_dispatcher),
):
    q = select(Patrol).order_by(Patrol.window_start)
    if date is not None:
        try:
            d = date_cls.fromisoformat(date)
        except ValueError:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail="date: ГГГГ-ММ-ДД")
        q = q.where(Patrol.patrol_date == d)
    if object_id is not None:
        q = q.where(Patrol.object_id == object_id)
    if status_filter is not None:
        q = q.where(Patrol.status == status_filter)
    patrols = list(db.scalars(q.limit(1000)))
    return [_patrol_out(p) for p in patrols]


@router.get("/patrols/{patrol_id}", response_model=PatrolOut)
def get_patrol(
    patrol_id: int,
    db=Depends(get_db),
    user: CurrentUser = Depends(require_dispatcher),
):
    p = db.get(Patrol, patrol_id)
    if p is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Обход не найден")
    return _patrol_out(p)
