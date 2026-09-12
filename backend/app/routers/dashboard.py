"""Дашборд диспетчера (этап 3: наполнение)."""
from fastapi import APIRouter, Depends

from app.core.deps import CurrentUser, require_dispatcher

router = APIRouter()


@router.get("/dashboard")
def dashboard(
    date: str | None = None,
    user: CurrentUser = Depends(require_dispatcher),
) -> dict:
    # Этап 3 (patrol_engine): агрегаты по объектам за дату
    return {"detail": "Реализация на этапе 3 (patrol_engine)"}
