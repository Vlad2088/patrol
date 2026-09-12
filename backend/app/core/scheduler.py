"""Планировщик фоновых задач: материализация обходов + автофиксация нарушений."""
from datetime import datetime, timezone

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI

from app.db import SessionLocal
from app.services.patrol_engine import detect_violations, materialize_patrols

scheduler = BackgroundScheduler(timezone="UTC")


def _tick() -> None:
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        materialize_patrols(db, now)
        detect_violations(db, now)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def start_scheduler(app: FastAPI) -> None:
    scheduler.add_job(_tick, "interval", minutes=1, id="patrol_tick", replace_existing=True)
    scheduler.start()


def stop_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
