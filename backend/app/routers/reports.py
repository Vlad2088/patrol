"""Отчёты: CSV (utf-8-sig для Excel) и XLSX по обходам и нарушениям."""
import csv
import io
from datetime import date as date_cls, datetime

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from app.core.deps import CurrentUser, require_dispatcher
from app.db import get_db
from app.models import Checkpoint, Object, Patrol, Route, ScanEvent, User, Violation

router = APIRouter()

PATROL_HEADER = [
    "Дата", "Объект", "Маршрут", "Начал (охранник)", "Окно начало", "Окно конец",
    "Статус", "Точек пройдено", "Точек всего",
]
VIOLATION_HEADER = ["Дата фиксации", "Тип", "Объект", "Дата обхода", "Детали"]


def _period(from_: str | None, to: str | None) -> tuple[date_cls, date_cls]:
    today = datetime.utcnow().date()
    d_from = date_cls.fromisoformat(from_) if from_ else today - date_cls.resolution * 30
    d_to = date_cls.fromisoformat(to) if to else today
    return d_from, d_to


def _patrol_rows(db) -> list[list]:
    patrols = list(db.scalars(select(Patrol).order_by(Patrol.window_start.desc()).limit(5000)))
    rows = []
    for p in patrols:
        guard = db.get(User, p.started_by_id) if p.started_by_id else None
        obj = db.get(Object, p.object_id)
        route = db.get(Route, p.route_id)
        rows.append([
            p.patrol_date.isoformat(),
            obj.name if obj else "",
            route.name if route else "",
            guard.full_name if guard else "",
            p.window_start.isoformat(),
            p.window_end.isoformat(),
            p.status.value,
            p.checkpoints_scanned,
            p.checkpoints_total,
        ])
    return rows


def _violation_rows(db) -> list[list]:
    violations = list(db.scalars(select(Violation).order_by(Violation.detected_at.desc()).limit(5000)))
    rows = []
    for v in violations:
        p = db.get(Patrol, v.patrol_id)
        obj = db.get(Object, p.object_id) if p else None
        details = "; ".join(f"{k}={v}" for k, v in (v.details or {}).items())
        rows.append([
            v.detected_at.isoformat(),
            v.kind.value,
            obj.name if obj else "",
            p.patrol_date.isoformat() if p else "",
            details[:200],
        ])
    return rows


def _csv_response(header: list, rows: list[list], filename: str) -> StreamingResponse:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(header)
    w.writerows(rows)
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue().encode("utf-8-sig")]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _xlsx_response(header: list, rows: list[list], filename: str) -> StreamingResponse:
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = filename.split(".")[0][:30]
    ws.append(header)
    for r in rows:
        ws.append(r)
    out = io.BytesIO()
    wb.save(out)
    out.seek(0)
    return StreamingResponse(
        out,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _export(db, kind: str, fmt: str, from_: str | None, to: str | None):
    d_from, d_to = _period(from_, to)
    if kind == "patrols":
        rows = [r for r in _patrol_rows(db) if d_from.isoformat() <= r[0] <= d_to.isoformat()]
        header, name = PATROL_HEADER, "patrols"
    else:
        rows = _violation_rows(db)
        header, name = VIOLATION_HEADER, "violations"
    stamp = datetime.utcnow().strftime("%Y%m%d")
    if fmt == "xlsx":
        return _xlsx_response(header, rows, f"{name}_{stamp}.xlsx")
    return _csv_response(header, rows, f"{name}_{stamp}.csv")


@router.get("/reports/patrols.csv")
def patrols_csv(from_: str | None = None, to: str | None = None,
                db=Depends(get_db), user: CurrentUser = Depends(require_dispatcher)):
    return _export(db, "patrols", "csv", from_, to)


@router.get("/reports/patrols.xlsx")
def patrols_xlsx(from_: str | None = None, to: str | None = None,
                 db=Depends(get_db), user: CurrentUser = Depends(require_dispatcher)):
    return _export(db, "patrols", "xlsx", from_, to)


@router.get("/reports/violations.csv")
def violations_csv(from_: str | None = None, to: str | None = None,
                   db=Depends(get_db), user: CurrentUser = Depends(require_dispatcher)):
    return _export(db, "violations", "csv", from_, to)


@router.get("/reports/violations.xlsx")
def violations_xlsx(from_: str | None = None, to: str | None = None,
                    db=Depends(get_db), user: CurrentUser = Depends(require_dispatcher)):
    return _export(db, "violations", "xlsx", from_, to)
