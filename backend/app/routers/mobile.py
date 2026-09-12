"""Мобильные эндпоинты (этап 3: sync/scans/start/finish)."""
from fastapi import APIRouter, Depends

from app.core.deps import CurrentUser, require_guard

router = APIRouter()


@router.get("/mobile/sync")
def sync(user: CurrentUser = Depends(require_guard)) -> dict:
    return {"detail": "Реализация на этапе 3 (mobile sync)"}
