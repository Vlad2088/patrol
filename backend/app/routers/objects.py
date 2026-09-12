"""Объекты: CRUD (диспетчер) + аудит."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from app.core.deps import CurrentUser, require_dispatcher
from app.db import get_db
from app.models import Object
from app.schemas import ObjectCreate, ObjectOut, ObjectUpdate
from app.services.audit import audit_log

router = APIRouter()


@router.get("/objects", response_model=list[ObjectOut])
def list_objects(
    db=Depends(get_db),
    user: CurrentUser = Depends(require_dispatcher),
) -> list[Object]:
    return list(db.scalars(select(Object).order_by(Object.name)))


@router.post("/objects", response_model=ObjectOut, status_code=201)
def create_object(
    body: ObjectCreate,
    db=Depends(get_db),
    user: CurrentUser = Depends(require_dispatcher),
) -> Object:
    obj = Object(name=body.name, address=body.address)
    db.add(obj)
    db.flush()
    audit_log(db, user.id, "create", "object", obj.id, {"name": body.name})
    db.commit()
    return obj


@router.patch("/objects/{object_id}", response_model=ObjectOut)
def update_object(
    object_id: int,
    body: ObjectUpdate,
    db=Depends(get_db),
    user: CurrentUser = Depends(require_dispatcher),
) -> Object:
    obj = db.get(Object, object_id)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Объект не найден")
    changes: dict = {}
    if body.name is not None:
        obj.name = body.name
        changes["name"] = body.name
    if body.address is not None:
        obj.address = body.address
        changes["address"] = body.address
    if body.is_active is not None:
        obj.is_active = body.is_active
        changes["is_active"] = body.is_active
    audit_log(db, user.id, "update", "object", obj.id, changes)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/objects/{object_id}", status_code=204)
def delete_object(
    object_id: int,
    db=Depends(get_db),
    user: CurrentUser = Depends(require_dispatcher),
) -> None:
    obj = db.get(Object, object_id)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Объект не найден")
    obj.is_active = False  # soft delete
    audit_log(db, user.id, "delete", "object", obj.id, {"name": obj.name})
    db.commit()
