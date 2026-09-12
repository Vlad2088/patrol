"""Расписания обходов: CRUD (диспетчер)."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from app.core.deps import CurrentUser, require_dispatcher
from app.db import get_db
from app.models import PatrolSchedule, Route
from app.schemas import ScheduleCreate, ScheduleOut
from app.services.audit import audit_log

router = APIRouter()


def _validate(db, body: ScheduleCreate) -> Route:
    route = db.get(Route, body.route_id)
    if route is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Маршрут не найден")

    if body.kind == "once" and body.once_date is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Для kind=once укажите once_date")
    if body.kind == "weekly" and not body.weekdays:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Для kind=weekly укажите weekdays")
    if body.kind == "shift" and body.shift_kind is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Для kind=shift укажите shift_kind")
    return route


@router.get("/schedules", response_model=list[ScheduleOut])
def list_schedules(
    route_id: int | None = None,
    db=Depends(get_db),
    user: CurrentUser = Depends(require_dispatcher),
):
    q = select(PatrolSchedule).order_by(PatrolSchedule.id)
    if route_id is not None:
        q = q.where(PatrolSchedule.route_id == route_id)
    return list(db.scalars(q))


@router.post("/schedules", response_model=ScheduleOut, status_code=201)
def create_schedule(
    body: ScheduleCreate,
    db=Depends(get_db),
    user: CurrentUser = Depends(require_dispatcher),
) -> PatrolSchedule:
    _validate(db, body)
    sched = PatrolSchedule(
        route_id=body.route_id,
        kind=body.kind,
        once_date=body.once_date if body.kind == "once" else None,
        weekdays=body.weekdays if body.kind == "weekly" else None,
        shift_kind=body.shift_kind if body.kind == "shift" else None,
        window_start=body.window_start,
        window_end=body.window_end,
    )
    db.add(sched)
    db.flush()
    audit_log(db, user.id, "create", "schedule", sched.id, {"kind": body.kind})
    db.commit()
    return sched


@router.patch("/schedules/{schedule_id}", response_model=ScheduleOut)
def update_schedule(
    schedule_id: int,
    body: ScheduleCreate,
    db=Depends(get_db),
    user: CurrentUser = Depends(require_dispatcher),
):
    sched = db.get(PatrolSchedule, schedule_id)
    if sched is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Расписание не найдено")
    _validate(db, body)
    sched.kind = body.kind
    sched.once_date = body.once_date if body.kind == "once" else None
    sched.weekdays = body.weekdays if body.kind == "weekly" else None
    sched.shift_kind = body.shift_kind if body.kind == "shift" else None
    sched.window_start = body.window_start
    sched.window_end = body.window_end
    audit_log(db, user.id, "update", "schedule", sched.id, {"kind": body.kind})
    db.commit()
    db.refresh(sched)
    return sched


@router.delete("/schedules/{schedule_id}", status_code=204)
def delete_schedule(
    schedule_id: int,
    db=Depends(get_db),
    user: CurrentUser = Depends(require_dispatcher),
) -> None:
    sched = db.get(PatrolSchedule, schedule_id)
    if sched is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Расписание не найдено")
    sched.is_active = False
    audit_log(db, user.id, "delete", "schedule", sched.id, {})
    db.commit()
