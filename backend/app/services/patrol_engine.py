"""Движок обходов: материализация расписаний, валидация сканов, нарушения."""
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import (
    Checkpoint,
    Patrol,
    PatrolSchedule,
    PatrolStatus,
    Route,
    ScanEvent,
    ScanResult,
    Shift,
    Violation,
    ViolationKind,
)

settings = get_settings()

# Локальный пояс сервера для материализации окон (dev: UTC; прод — по месту)
TZ = timezone.utc


def _window_for_date(sched: PatrolSchedule, d: date) -> tuple[datetime, datetime]:
    ws = datetime.combine(d, sched.window_start, tzinfo=TZ)
    we = datetime.combine(d, sched.window_end, tzinfo=TZ)
    if sched.window_end <= sched.window_start:  # окно через полночь
        we += timedelta(days=1)
    return ws, we


def materialize_patrols(db: Session, now: datetime) -> int:
    """Создаёт patrols из активных расписаний на горизонт +24ч. Идемпотентно."""
    horizon_end = now + timedelta(hours=settings.materialize_horizon_hours)
    created = 0
    scheds = list(
        db.scalars(select(PatrolSchedule).where(PatrolSchedule.is_active.is_(True)))
    )
    for sched in scheds:
        route = db.get(Route, sched.route_id)
        if route is None or not route.is_active:
            continue

        days: set[date] = set()
        if sched.kind == "once":
            if sched.once_date is not None and now.date() <= sched.once_date:
                days.add(sched.once_date)
        else:
            # daily / weekly / shift: смотрим 2 дня (окно может переходить через полночь)
            for offset in (0, 1):
                d = (now + timedelta(days=offset)).date()
                if sched.kind == "daily":
                    days.add(d)
                elif sched.kind == "weekly":
                    if sched.weekdays and d.isoweekday() in sched.weekdays:
                        days.add(d)
                elif sched.kind == "shift":
                    days.add(d)

        for d in days:
            ws, we = _window_for_date(sched, d)
            if we < now:  # окно уже полностью прошло — не создаём
                continue
            if ws > horizon_end:
                continue
            exists = db.scalar(
                select(Patrol.id).where(
                    Patrol.schedule_id == sched.id, Patrol.patrol_date == d
                )
            )
            if exists:
                continue
            total = len(
                list(
                    db.scalars(
                        select(Checkpoint.id).where(Checkpoint.route_id == route.id)
                    )
                )
            )
            db.add(
                Patrol(
                    object_id=route.object_id,
                    route_id=route.id,
                    schedule_id=sched.id,
                    patrol_date=d,
                    window_start=ws,
                    window_end=we,
                    checkpoints_total=total,
                )
            )
            created += 1
    if created:
        db.commit()
    return created


def validate_scan(
    db: Session,
    patrol: Patrol,
    checkpoint: Checkpoint,
    guard_id: int,
    client_uuid: str,
    scanned_at: datetime,
    now: datetime,
) -> tuple[ScanResult, ScanEvent | None]:
    """Серверная валидация одного скана по правилам ТЗ (раздел 6)."""
    if client_uuid and db.scalar(
        select(ScanEvent.id).where(ScanEvent.client_uuid == client_uuid)
    ):
        return ScanResult.DUPLICATE, None

    if patrol.status not in (PatrolStatus.PLANNED, PatrolStatus.IN_PROGRESS):
        return ScanResult.PATROL_CLOSED, None

    if checkpoint.route_id != patrol.route_id:
        return ScanResult.WRONG_CHECKPOINT, None

    # порядок: все точки с меньшим order_num должны быть отмечены
    done_orders = set(
        db.scalars(
            select(ScanEvent.checkpoint_id).where(ScanEvent.patrol_id == patrol.id)
        )
    )
    prior = list(
        db.scalars(
            select(Checkpoint)
            .where(
                Checkpoint.route_id == patrol.route_id,
                Checkpoint.order_num < checkpoint.order_num,
            )
            .order_by(Checkpoint.order_num)
        )
    )
    if any(cp.id not in done_orders for cp in prior):
        return ScanResult.OUT_OF_ORDER, None

    out_of_window = not (
        patrol.window_start - timedelta(minutes=settings.window_grace_before_min)
        <= scanned_at
        <= patrol.window_end + timedelta(minutes=settings.window_grace_after_min)
    )

    event = ScanEvent(
        patrol_id=patrol.id,
        checkpoint_id=checkpoint.id,
        guard_id=guard_id,
        scanned_at=scanned_at,
        client_uuid=client_uuid,
        out_of_window=out_of_window,
    )
    db.add(event)

    patrol.checkpoints_scanned += 1
    if patrol.status == PatrolStatus.PLANNED:
        patrol.status = PatrolStatus.IN_PROGRESS
        patrol.started_by_id = guard_id
        patrol.started_at = scanned_at
    if patrol.checkpoints_scanned >= patrol.checkpoints_total > 0:
        patrol.status = PatrolStatus.COMPLETED
        patrol.finished_at = scanned_at
    db.flush()
    return (ScanResult.OUT_OF_WINDOW if out_of_window else ScanResult.ACCEPTED), event


def detect_violations(db: Session, now: datetime) -> int:
    """Автофиксация нарушений по истечении окна (+grace). Идемпотентна."""
    deadline = now - timedelta(minutes=settings.window_grace_after_min)
    detected = 0
    overdue = list(
        db.scalars(
            select(Patrol).where(
                Patrol.window_end < deadline,
                Patrol.status.in_([PatrolStatus.PLANNED, PatrolStatus.IN_PROGRESS]),
            )
        )
    )
    for p in overdue:
        has_missed_patrol = db.scalar(
            select(Violation.id).where(
                Violation.patrol_id == p.id,
                Violation.kind == ViolationKind.MISSED_PATROL,
            )
        )
        has_missed_points = db.scalar(
            select(Violation.id).where(
                Violation.patrol_id == p.id,
                Violation.kind == ViolationKind.MISSED_POINTS,
            )
        )
        if p.checkpoints_scanned == 0:
            if not has_missed_patrol:
                db.add(
                    Violation(
                        patrol_id=p.id,
                        kind=ViolationKind.MISSED_PATROL,
                        details={"window_start": p.window_start.isoformat(),
                                 "window_end": p.window_end.isoformat()},
                    )
                )
                p.status = PatrolStatus.MISSED
                detected += 1
        else:
            if not has_missed_points:
                done_ids = set(
                    db.scalars(
                        select(ScanEvent.checkpoint_id).where(
                            ScanEvent.patrol_id == p.id
                        )
                    )
                )
                missed = [
                    cp.code
                    for cp in db.scalars(
                        select(Checkpoint)
                        .where(Checkpoint.route_id == p.route_id)
                        .order_by(Checkpoint.order_num)
                    )
                    if cp.id not in done_ids
                ]
                db.add(
                    Violation(
                        patrol_id=p.id,
                        kind=ViolationKind.MISSED_POINTS,
                        details={
                            "missed_codes": missed,
                            "scanned": p.checkpoints_scanned,
                            "total": p.checkpoints_total,
                        },
                    )
                )
                p.status = PatrolStatus.PARTIAL
                detected += 1
    if detected:
        db.commit()
    return detected
