"""Управление охранниками (CRUD диспетчера) + аудит."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select

from app.core.deps import CurrentUser, require_dispatcher
from app.db import get_db
from app.models import AuditLog, User, UserRole
from app.schemas import GuardCreate, GuardOut, GuardUpdate
from app.services.audit import audit_log

router = APIRouter()


@router.get("/guards", response_model=list[GuardOut])
def list_guards(
    db=Depends(get_db),
    user: CurrentUser = Depends(require_dispatcher),
) -> list[User]:
    return list(
        db.scalars(
            select(User)
            .where(User.role == UserRole.GUARD)
            .order_by(User.full_name)
        )
    )


@router.post("/guards", response_model=GuardOut, status_code=201)
def create_guard(
    body: GuardCreate,
    db=Depends(get_db),
    user: CurrentUser = Depends(require_dispatcher),
) -> User:
    exists = db.scalar(select(func.count()).select_from(User).where(User.login == body.login))
    if exists:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Логин уже занят")

    from app.core.security import hash_password

    guard = User(
        login=body.login,
        password_hash=hash_password(body.password),
        full_name=body.full_name,
        role=UserRole.GUARD,
    )
    db.add(guard)
    db.flush()
    audit_log(db, user.id, "create", "guard", guard.id, {"login": body.login})
    db.commit()
    return guard


@router.patch("/guards/{guard_id}", response_model=GuardOut)
def update_guard(
    guard_id: int,
    body: GuardUpdate,
    db=Depends(get_db),
    user: CurrentUser = Depends(require_dispatcher),
) -> User:
    guard = db.get(User, guard_id)
    if guard is None or guard.role != UserRole.GUARD:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Охранник не найден")

    changes: dict = {}
    if body.full_name is not None:
        changes["full_name"] = body.full_name
        guard.full_name = body.full_name
    if body.is_active is not None:
        changes["is_active"] = body.is_active
        guard.is_active = body.is_active
    if body.password is not None:
        from app.core.security import hash_password

        guard.password_hash = hash_password(body.password)
        changes["password"] = "***"
    audit_log(db, user.id, "update", "guard", guard.id, changes)
    db.commit()
    db.refresh(guard)
    return guard


@router.delete("/guards/{guard_id}", status_code=204)
def delete_guard(
    guard_id: int,
    db=Depends(get_db),
    user: CurrentUser = Depends(require_dispatcher),
) -> None:
    guard = db.get(User, guard_id)
    if guard is None or guard.role != UserRole.GUARD:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Охранник не найден")
    guard.is_active = False  # soft delete: история отметок сохраняется
    audit_log(db, user.id, "delete", "guard", guard.id, {"login": guard.login})
    db.commit()
