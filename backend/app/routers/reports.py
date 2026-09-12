"""Отчёты CSV/Excel (этап 3)."""
from fastapi import APIRouter, Depends

from app.core.deps import CurrentUser, require_dispatcher

router = APIRouter()


@router.get("/reports/patrols.csv")
def patrols_csv(user: CurrentUser = Depends(require_dispatcher)) -> dict:
    return {"detail": "Реализация на этапе 3 (reports)"}
