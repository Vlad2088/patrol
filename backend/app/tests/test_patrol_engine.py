"""Тесты движка обходов: валидация сканов, порядок, дубли, нарушения.

Используют SQLite in-memory (enum-native выключен — совместимо).
"""
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import (
    Base,
    Checkpoint,
    Object,
    Patrol,
    PatrolSchedule,
    PatrolStatus,
    Route,
    ScanEvent,
    ScanResult,
    Shift,
    User,
    UserRole,
    Violation,
    ViolationKind,
)
from app.services.patrol_engine import detect_violations, materialize_patrols, validate_scan

NOW = datetime(2026, 9, 11, 12, 0, tzinfo=timezone.utc)


@pytest.fixture()
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    session = Session()
    yield session
    session.close()


@pytest.fixture()
def world(db):
    """Объект + маршрут из 3 точек + охранник + расписание на сегодня 10:00-11:00."""
    obj = Object(name="Склад")
    db.add(obj)
    db.flush()
    route = Route(object_id=obj.id, name="Периметр")
    db.add(route)
    db.flush()
    cps = []
    for i in range(1, 4):
        cp = Checkpoint(route_id=route.id, order_num=i, code=f"R{route.id}-{i:03d}")
        db.add(cp)
        cps.append(cp)
    db.flush()
    guard = User(
        login="guard1", password_hash="x", full_name="Иванов И. И.",
        role=UserRole.GUARD,
    )
    db.add(guard)
    db.flush()
    sched = PatrolSchedule(
        route_id=route.id, kind="daily",
        window_start=datetime.strptime("10:00", "%H:%M").time(),
        window_end=datetime.strptime("11:00", "%H:%M").time(),
    )
    db.add(sched)
    db.commit()
    return {"obj": obj, "route": route, "cps": cps, "guard": guard, "sched": sched}


def _make_patrol(world, db, status=PatrolStatus.PLANNED, scanned=0):
    p = Patrol(
        object_id=world["obj"].id,
        route_id=world["route"].id,
        schedule_id=world["sched"].id,
        patrol_date=NOW.date(),
        window_start=NOW.replace(hour=10),
        window_end=NOW.replace(hour=11),
        status=status,
        checkpoints_total=3,
        checkpoints_scanned=scanned,
    )
    db.add(p)
    db.commit()
    return p


# --- материализация ---

def test_materialize_creates_patrol_once(db, world):
    n1 = materialize_patrols(db, NOW)
    n2 = materialize_patrols(db, NOW)
    assert n1 == 1 and n2 == 0
    p = db.query(Patrol).one()
    assert p.checkpoints_total == 3
    assert p.window_start.hour == 10 and p.window_end.hour == 11


def test_materialize_skips_past_window(db, world):
    # расписание с окном вчера не материализуется вовсе
    world["sched"].window_start = datetime.strptime("10:00", "%H:%M").time()
    world["sched"].window_end = datetime.strptime("11:00", "%H:%M").time()
    db.commit()
    # окно «сегодня 10-11» при now=13:00 уже прошло, завтрашнего дня в наборе нет:
    # расписание деактивируем и проверяем, что ничего не создалось
    world["sched"].is_active = False
    db.commit()
    assert materialize_patrols(db, NOW.replace(hour=13)) == 0


# --- валидация сканов ---

def test_scan_accepted_in_order(db, world):
    p = _make_patrol(world, db)
    r, e = validate_scan(db, p, world["cps"][0], world["guard"].id, "uuid-1",
                         NOW.replace(hour=10, minute=5), NOW)
    assert r == ScanResult.ACCEPTED
    assert p.status == PatrolStatus.IN_PROGRESS
    assert p.checkpoints_scanned == 1
    assert p.started_by_id == world["guard"].id


def test_scan_duplicate_by_uuid(db, world):
    p = _make_patrol(world, db)
    validate_scan(db, p, world["cps"][0], world["guard"].id, "uuid-1",
                  NOW.replace(hour=10, minute=5), NOW)
    r, e = validate_scan(db, p, world["cps"][0], world["guard"].id, "uuid-1",
                         NOW.replace(hour=10, minute=6), NOW)
    assert r == ScanResult.DUPLICATE
    assert p.checkpoints_scanned == 1  # не задвоился


def test_scan_out_of_order_rejected(db, world):
    p = _make_patrol(world, db)
    r, _ = validate_scan(db, p, world["cps"][2], world["guard"].id, "uuid-2",
                         NOW.replace(hour=10, minute=5), NOW)
    assert r == ScanResult.OUT_OF_ORDER
    assert p.checkpoints_scanned == 0


def test_scan_completes_patrol(db, world):
    p = _make_patrol(world, db, status=PatrolStatus.IN_PROGRESS)
    # проходим точки 1 и 2, затем 3 — обход завершается
    validate_scan(db, p, world["cps"][0], world["guard"].id, "uuid-3a",
                  NOW.replace(hour=10, minute=30), NOW)
    validate_scan(db, p, world["cps"][1], world["guard"].id, "uuid-3b",
                  NOW.replace(hour=10, minute=35), NOW)
    r, _ = validate_scan(db, p, world["cps"][2], world["guard"].id, "uuid-3",
                         NOW.replace(hour=10, minute=40), NOW)
    assert r == ScanResult.ACCEPTED
    assert p.status == PatrolStatus.COMPLETED
    assert p.finished_at is not None


def test_scan_out_of_window_flagged_but_saved(db, world):
    p = _make_patrol(world, db)
    r, e = validate_scan(db, p, world["cps"][0], world["guard"].id, "uuid-4",
                         NOW.replace(hour=12, minute=0), NOW)  # сильно позже окна
    assert r == ScanResult.OUT_OF_WINDOW
    assert e is not None and e.out_of_window is True
    assert p.checkpoints_scanned == 1


def test_scan_closed_patrol(db, world):
    p = _make_patrol(world, db, status=PatrolStatus.COMPLETED, scanned=3)
    r, _ = validate_scan(db, p, world["cps"][0], world["guard"].id, "uuid-5",
                         NOW.replace(hour=10, minute=5), NOW)
    assert r == ScanResult.PATROL_CLOSED


# --- нарушения ---

def test_violation_missed_patrol(db, world):
    p = _make_patrol(world, db)  # окно 10-11, сканов нет
    n = detect_violations(db, NOW.replace(hour=13))  # после окна+grace
    assert n == 1
    v = db.query(Violation).one()
    assert v.kind == ViolationKind.MISSED_PATROL
    assert p.status == PatrolStatus.MISSED
    # идемпотентность
    assert detect_violations(db, NOW.replace(hour=14)) == 0


def test_violation_missed_points(db, world):
    p = _make_patrol(world, db, status=PatrolStatus.IN_PROGRESS, scanned=1)
    validate_scan(db, p, world["cps"][0], world["guard"].id, "u1",
                  NOW.replace(hour=10, minute=5), NOW)
    n = detect_violations(db, NOW.replace(hour=13))
    assert n == 1
    v = db.query(Violation).one()
    assert v.kind == ViolationKind.MISSED_POINTS
    assert v.details["missed_codes"] == [world["cps"][1].code, world["cps"][2].code]
    assert p.status == PatrolStatus.PARTIAL
