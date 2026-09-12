"""Мобильные эндпоинты охранника: sync, старт, сканы, финиш, история."""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from app.core.deps import CurrentUser, require_guard
from app.db import get_db
from app.models import (
    Checkpoint,
    Patrol,
    PatrolStatus,
    Route,
    ScanEvent,
    ScanResult,
    Shift,
)
from app.schemas import (
    MobileCheckpoint,
    MobilePatrol,
    MobileRoute,
    MobileShift,
    MobileSyncOut,
    PatrolStartOut,
    ScanBatchIn,
    ScanResultOut,
)
from app.services.patrol_engine import validate_scan

router = APIRouter()


@router.get("/mobile/sync", response_model=MobileSyncOut)
def sync(
    db=Depends(get_db),
    user: CurrentUser = Depends(require_guard),
) -> MobileSyncOut:
    """Полный пакет для офлайн-работы: маршруты объектов моих смен, точки,
    плановые/активные обходы на 48ч, мои смены."""
    now = datetime.now(timezone.utc)
    until = now + timedelta(hours=48)
    since = now - timedelta(hours=24)

    my_object_ids = set(
        db.scalars(
            select(Shift.object_id).where(
                Shift.guard_id == user.id, Shift.ends_at > since
            )
        )
    )
    routes = list(
        db.scalars(
            select(Route).where(
                Route.object_id.in_(my_object_ids), Route.is_active.is_(True)
            )
        )
    )
    route_ids = [r.id for r in routes]
    checkpoints = (
        list(db.scalars(select(Checkpoint).where(Checkpoint.route_id.in_(route_ids))))
        if route_ids
        else []
    )
    patrols = list(
        db.scalars(
            select(Patrol).where(
                Patrol.object_id.in_(my_object_ids),
                Patrol.window_end > since,
                Patrol.window_start < until,
                Patrol.status.in_(
                    [PatrolStatus.PLANNED, PatrolStatus.IN_PROGRESS]
                ),
            )
        )
    )
    shifts = list(
        db.scalars(
            select(Shift).where(Shift.guard_id == user.id, Shift.ends_at > since)
        )
    )
    return MobileSyncOut(
        routes=[MobileRoute.model_validate(r) for r in routes],
        checkpoints=[MobileCheckpoint.model_validate(c) for c in checkpoints],
        patrols=[MobilePatrol.model_validate(p) for p in patrols],
        shifts=[MobileShift.model_validate(s) for s in shifts],
    )


@router.post("/mobile/patrols/{patrol_id}/start", response_model=PatrolStartOut)
def start_patrol(
    patrol_id: int,
    db=Depends(get_db),
    user: CurrentUser = Depends(require_guard),
) -> PatrolStartOut:
    patrol = db.get(Patrol, patrol_id)
    if patrol is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Обход не найден")
    if patrol.status not in (PatrolStatus.PLANNED, PatrolStatus.IN_PROGRESS):
        return PatrolStartOut(ok=False, message="Обход уже завершён или пропущен")

    # охранник должен быть в смене на объекте (по времени — с допуском grace)
    from app.config import get_settings

    st = get_settings()
    now = datetime.now(timezone.utc)
    on_shift = db.scalar(
        select(Shift.id).where(
            Shift.guard_id == user.id,
            Shift.object_id == patrol.object_id,
            Shift.starts_at - timedelta(minutes=st.window_grace_before_min) <= now,
            Shift.ends_at + timedelta(minutes=st.window_grace_after_min) >= now,
        )
    )
    if not on_shift:
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail="Нет активной смены на этом объекте"
        )

    if patrol.status == PatrolStatus.PLANNED:
        patrol.status = PatrolStatus.IN_PROGRESS
        patrol.started_by_id = user.id
        patrol.started_at = now
        db.commit()
        db.refresh(patrol)
    return PatrolStartOut(ok=True, patrol=MobilePatrol.model_validate(patrol))


@router.post("/mobile/scans", response_model=list[ScanResultOut])
def submit_scans(
    body: ScanBatchIn,
    db=Depends(get_db),
    user: CurrentUser = Depends(require_guard),
):
    """Батч отметок из офлайн-очереди. Ответ по каждой — для синхронизации Room."""
    now = datetime.now(timezone.utc)
    results: list[ScanResultOut] = []
    for scan in body.scans:
        cp = db.scalar(select(Checkpoint).where(Checkpoint.code == scan.checkpoint_code))
        if cp is None:
            results.append(
                ScanResultOut(
                    client_uuid=scan.client_uuid,
                    result=ScanResult.WRONG_CHECKPOINT,
                    message="Точка не найдена",
                )
            )
            continue
        patrol = db.scalar(
            select(Patrol).where(Patrol.route_id == cp.route_id,
                                 Patrol.status.in_([PatrolStatus.PLANNED, PatrolStatus.IN_PROGRESS]))
            .order_by(Patrol.window_start.desc()).limit(1)
        )
        if patrol is None:
            results.append(
                ScanResultOut(
                    client_uuid=scan.client_uuid,
                    result=ScanResult.PATROL_CLOSED,
                    message="Нет активного обхода для этой точки",
                )
            )
            continue
        result, _event = validate_scan(
            db, patrol, cp, user.id, scan.client_uuid, scan.scanned_at, now
        )
        db.commit()
        msg = {
            ScanResult.ACCEPTED: "Принято",
            ScanResult.DUPLICATE: "Дубль (уже была)",
            ScanResult.WRONG_CHECKPOINT: "Точка не из этого маршрута",
            ScanResult.OUT_OF_ORDER: "Нарушен порядок точек",
            ScanResult.PATROL_CLOSED: "Обход закрыт",
            ScanResult.OUT_OF_WINDOW: "Принято вне окна (зафиксировано)",
        }.get(result, "")
        results.append(ScanResultOut(client_uuid=scan.client_uuid, result=result, message=msg))
    return results


@router.post("/mobile/patrols/{patrol_id}/finish", response_model=PatrolStartOut)
def finish_patrol(
    patrol_id: int,
    db=Depends(get_db),
    user: CurrentUser = Depends(require_guard),
) -> PatrolStartOut:
    patrol = db.get(Patrol, patrol_id)
    if patrol is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Обход не найден")
    if patrol.status != PatrolStatus.IN_PROGRESS:
        return PatrolStartOut(ok=False, message=f"Статус: {patrol.status}")
    if patrol.checkpoints_scanned < patrol.checkpoints_total:
        # частичный: статус частично проставит автофиксация после окна,
        # но факт завершения фиксируем сразу
        patrol.finished_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(patrol)
        return PatrolStartOut(
            ok=True,
            patrol=MobilePatrol.model_validate(patrol),
            message="Завершён частично (будет проверен автофиксацией)",
        )
    return PatrolStartOut(ok=True, patrol=MobilePatrol.model_validate(patrol))


@router.get("/mobile/history", response_model=list[MobilePatrol])
def history(
    from_: str | None = None,
    to: str | None = None,
    db=Depends(get_db),
    user: CurrentUser = Depends(require_guard),
):
    """История обходов, где я делал отметки."""
    from datetime import date as date_cls

    q = (
        select(Patrol)
        .join(ScanEvent, ScanEvent.patrol_id == Patrol.id)
        .where(ScanEvent.guard_id == user.id)
        .order_by(Patrol.window_start.desc())
        .distinct()
        .limit(200)
    )
    if from_:
        q = q.where(Patrol.patrol_date >= date_cls.fromisoformat(from_))
    if to:
        q = q.where(Patrol.patrol_date <= date_cls.fromisoformat(to))
    return [MobilePatrol.model_validate(p) for p in db.scalars(q)]
