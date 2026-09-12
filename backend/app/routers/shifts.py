"""Смены: назначение охранников на объекты (диспетчер)."""
from datetime import date as date_cls, datetime, time, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from app.core.deps import CurrentUser, require_dispatcher
from app.db import get_db
from app.models import Object, Shift, User, UserRole
from app.schemas import ShiftCreate, ShiftOut
from app.services.audit import audit_log

router = APIRouter()


def _shift_out(s: Shift) -> ShiftOut:
    return ShiftOut(
        id=s.id,
        object_id=s.object_id,
        guard_id=s.guard_id,
        starts_at=s.starts_at,
        ends_at=s.ends_at,
        guard_full_name=s.guard.full_name if s.guard else "",
        object_name=s.object.name if s.object else "",
    )


@router.get("/shifts", response_model=list[ShiftOut])
def list_shifts(
    object_id: int | None = None,
    date: str | None = None,
    db=Depends(get_db),
    user: CurrentUser = Depends(require_dispatcher),
):
    q = select(Shift).order_by(Shift.starts_at.desc())
    if object_id is not None:
        q = q.where(Shift.object_id == object_id)
    if date is not None:
        try:
            d = date_cls.fromisoformat(date)
        except ValueError:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY, detail="date: ожидается ГГГГ-ММ-ДД"
            )
        day_start = datetime.combine(d, time.min)
        day_end = day_start + timedelta(days=1)
        q = q.where(Shift.starts_at < day_end, Shift.ends_at > day_start)
    shifts = list(db.scalars(q.limit(500)))
    return [_shift_out(s) for s in shifts]


@router.post("/shifts", response_model=ShiftOut, status_code=201)
def create_shift(
    body: ShiftCreate,
    db=Depends(get_db),
    user: CurrentUser = Depends(require_dispatcher),
):
    obj = db.get(Object, body.object_id)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Объект не найден")
    guard = db.get(User, body.guard_id)
    if guard is None or guard.role != UserRole.GUARD:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Охранник не найден")
    if not guard.is_active:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Охранник отключён")

    shift = Shift(
        object_id=body.object_id,
        guard_id=body.guard_id,
        starts_at=body.starts_at,
        ends_at=body.ends_at,
    )
    db.add(shift)
    db.flush()
    audit_log(
        db, user.id, "create", "shift", shift.id,
        {"object_id": body.object_id, "guard_id": body.guard_id},
    )
    db.commit()
    return _shift_out(shift)


@router.delete("/shifts/{shift_id}", status_code=204)
def delete_shift(
    shift_id: int,
    db=Depends(get_db),
    user: CurrentUser = Depends(require_dispatcher),
) -> None:
    shift = db.get(Shift, shift_id)
    if shift is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Смена не найдена")
    db.delete(shift)
    audit_log(db, user.id, "delete", "shift", shift_id, {})
    db.commit()
