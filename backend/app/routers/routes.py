"""Маршруты и контрольные точки + QR-PDF (диспетчер)."""
import io
from datetime import datetime

import qrcode
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from sqlalchemy import func, select

from app.core.deps import CurrentUser, require_dispatcher
from app.db import get_db
from app.models import Checkpoint, Object, Route
from app.schemas import (
    CheckpointBatchCreate,
    CheckpointOut,
    CheckpointUpdate,
    RouteCreate,
    RouteOut,
)
from app.services.audit import audit_log

router = APIRouter()


def _get_route(db, route_id: int) -> Route:
    route = db.get(Route, route_id)
    if route is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Маршрут не найден")
    return route


@router.get("/routes", response_model=list[RouteOut])
def list_routes(
    object_id: int | None = None,
    db=Depends(get_db),
    user: CurrentUser = Depends(require_dispatcher),
):
    q = select(Route).order_by(Route.name)
    if object_id is not None:
        q = q.where(Route.object_id == object_id)
    routes = list(db.scalars(q))
    counts = dict(
        db.execute(
            select(Checkpoint.route_id, func.count())
            .group_by(Checkpoint.route_id)
        ).all()
    )
    return [
        RouteOut(
            id=r.id,
            object_id=r.object_id,
            name=r.name,
            is_active=r.is_active,
            checkpoints_count=counts.get(r.id, 0),
        )
        for r in routes
    ]


@router.post("/routes", response_model=RouteOut, status_code=201)
def create_route(
    body: RouteCreate,
    db=Depends(get_db),
    user: CurrentUser = Depends(require_dispatcher),
) -> RouteOut:
    obj = db.get(Object, body.object_id)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Объект не найден")
    route = Route(object_id=body.object_id, name=body.name)
    db.add(route)
    db.flush()
    audit_log(db, user.id, "create", "route", route.id, {"name": body.name})
    db.commit()
    return RouteOut(
        id=route.id,
        object_id=route.object_id,
        name=route.name,
        is_active=route.is_active,
        checkpoints_count=0,
    )


@router.get("/routes/{route_id}/checkpoints", response_model=list[CheckpointOut])
def list_checkpoints(
    route_id: int,
    db=Depends(get_db),
    user: CurrentUser = Depends(require_dispatcher),
):
    _get_route(db, route_id)
    return list(
        db.scalars(
            select(Checkpoint)
            .where(Checkpoint.route_id == route_id)
            .order_by(Checkpoint.order_num)
        )
    )


@router.post("/routes/{route_id}/checkpoints", response_model=list[CheckpointOut], status_code=201)
def create_checkpoints(
    route_id: int,
    body: CheckpointBatchCreate,
    db=Depends(get_db),
    user: CurrentUser = Depends(require_dispatcher),
):
    """Массовое добавление точек в конец маршрута. Коды: R{route}-{order:03d}."""
    route = _get_route(db, route_id)
    max_order = db.scalar(
        select(func.max(Checkpoint.order_num)).where(Checkpoint.route_id == route_id)
    ) or 0
    total = max_order + len(body.items)
    if total > 30:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail=f"Маршрут ограничен 30 точками (сейчас {max_order} + {len(body.items)})",
        )

    created: list[Checkpoint] = []
    for i, item in enumerate(body.items, start=1):
        cp = Checkpoint(
            route_id=route_id,
            order_num=max_order + i,
            code=f"R{route_id}-{max_order + i:03d}",
            name=item.name,
        )
        db.add(cp)
        created.append(cp)
    db.flush()
    audit_log(
        db, user.id, "create", "checkpoints", route_id, {"added": len(body.items), "total": total}
    )
    db.commit()
    return created


@router.patch("/checkpoints/{checkpoint_id}", response_model=CheckpointOut)
def update_checkpoint(
    checkpoint_id: int,
    body: CheckpointUpdate,
    db=Depends(get_db),
    user: CurrentUser = Depends(require_dispatcher),
):
    cp = db.get(Checkpoint, checkpoint_id)
    if cp is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Точка не найдена")
    if body.name is not None:
        cp.name = body.name
    audit_log(db, user.id, "update", "checkpoint", cp.id, {"name": body.name})
    db.commit()
    db.refresh(cp)
    return cp


@router.delete("/checkpoints/{checkpoint_id}", status_code=204)
def delete_checkpoint(
    checkpoint_id: int,
    db=Depends(get_db),
    user: CurrentUser = Depends(require_dispatcher),
) -> None:
    """Удаление последней точки маршрута (порядок остальных не меняется)."""
    cp = db.get(Checkpoint, checkpoint_id)
    if cp is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Точка не найдена")
    max_order = db.scalar(
        select(func.max(Checkpoint.order_num)).where(Checkpoint.route_id == cp.route_id)
    )
    if cp.order_num != max_order:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="Удалять можно только последнюю точку маршрута",
        )
    route_id = cp.route_id
    db.delete(cp)
    audit_log(db, user.id, "delete", "checkpoint", checkpoint_id, {"route_id": route_id})
    db.commit()


@router.get("/routes/{route_id}/qr.pdf")
def route_qr_pdf(
    route_id: int,
    db=Depends(get_db),
    user: CurrentUser = Depends(require_dispatcher),
) -> StreamingResponse:
    """PDF с QR-наклейками всех точек маршрута (печать)."""
    route = _get_route(db, route_id)
    cps = list(
        db.scalars(
            select(Checkpoint)
            .where(Checkpoint.route_id == route_id)
            .order_by(Checkpoint.order_num)
        )
    )
    if not cps:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="В маршруте нет точек")

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    width, height = A4
    label_w, label_h = 70 * mm, 37 * mm
    cols, rows = 2, 7  # 14 наклеек на страницу

    for page_start in range(0, len(cps), cols * rows):
        c.setFont("Helvetica", 8)
        c.drawString(
            15 * mm,
            height - 10 * mm,
            f"{route.name} — QR-наклейки (стр. {page_start // (cols * rows) + 1})",
        )
        for idx, cp in enumerate(cps[page_start : page_start + cols * rows]):
            col = idx % cols
            row = idx // cols
            x = 15 * mm + col * (label_w + 5 * mm)
            y = height - 18 * mm - (row + 1) * label_h - row * 3 * mm
            qr = qrcode.QRCode(border=1, box_size=6)
            qr.add_data(cp.code)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            img_buf = io.BytesIO()
            img.save(img_buf, format="PNG")
            from PIL import Image as PILImage

            pil = PILImage.open(img_buf)
            from reportlab.lib.utils import ImageReader

            qr_size = 22 * mm
            c.drawImage(ImageReader(pil), x, y + 8 * mm, qr_size, qr_size)
            c.setFont("Helvetica-Bold", 10)
            c.drawString(x + qr_size + 4 * mm, y + label_h - 12 * mm, cp.code)
            c.setFont("Helvetica", 8)
            c.drawString(
                x + qr_size + 4 * mm,
                y + label_h - 18 * mm,
                (cp.name or "")[:28],
            )
        c.showPage()
    c.save()
    buf.seek(0)
    filename = f"route_{route_id}_qr_{datetime.utcnow():%Y%m%d}.pdf"
    return StreamingResponse(
        buf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
