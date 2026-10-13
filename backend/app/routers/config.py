"""Публичный конфиг для клиентов: часовой пояс объектов."""
from fastapi import APIRouter
from pydantic import BaseModel

from app.config import get_settings

router = APIRouter()


class ConfigOut(BaseModel):
    facility_tz: str


@router.get("/config", response_model=ConfigOut)
def get_config() -> ConfigOut:
    """Пояс объекта: клиенты рендерят все времена в нём, а не в своём поясе."""
    return ConfigOut(facility_tz=get_settings().facility_tz)
