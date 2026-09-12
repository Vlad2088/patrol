"""Pydantic v2 схемы API."""
from datetime import date, datetime, time

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models import (
    PatrolStatus,
    ScheduleKind,
    ShiftKind,
    UserRole,
    ViolationKind,
)

# --- Auth ---


class LoginIn(BaseModel):
    login: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=6, max_length=128)


class TokenPair(BaseModel):
    access: str
    refresh: str
    role: UserRole
    full_name: str


class RefreshIn(BaseModel):
    refresh: str


# --- Users (guards) ---


class GuardCreate(BaseModel):
    login: str = Field(min_length=3, max_length=64, pattern=r"^[a-zA-Z0-9_.-]+$")
    password: str = Field(min_length=6, max_length=128)
    full_name: str = Field(min_length=3, max_length=255)


class GuardUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=3, max_length=255)
    password: str | None = Field(default=None, min_length=6, max_length=128)
    is_active: bool | None = None


class GuardOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    login: str
    full_name: str
    role: UserRole
    is_active: bool
    created_at: datetime


# --- Objects ---


class ObjectCreate(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    address: str | None = Field(default=None, max_length=500)


class ObjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=255)
    address: str | None = Field(default=None, max_length=500)
    is_active: bool | None = None


class ObjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    address: str | None
    is_active: bool


# --- Routes & Checkpoints ---


class RouteCreate(BaseModel):
    object_id: int
    name: str = Field(min_length=2, max_length=255)


class RouteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    object_id: int
    name: str
    is_active: bool
    checkpoints_count: int = 0


class CheckpointCreate(BaseModel):
    name: str | None = Field(default=None, max_length=255)


class CheckpointBatchCreate(BaseModel):
    """Массовое создание: N точек подряд, коды генерирует сервер."""
    items: list[CheckpointCreate] = Field(min_length=1, max_length=30)


class CheckpointOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    route_id: int
    order_num: int
    code: str
    name: str | None


class CheckpointUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=255)


# --- Schedules ---


class ScheduleCreate(BaseModel):
    route_id: int
    kind: ScheduleKind
    once_date: date | None = None
    weekdays: list[int] | None = Field(default=None, max_length=7)
    shift_kind: ShiftKind | None = None
    window_start: time
    window_end: time

    @field_validator("weekdays")
    @classmethod
    def weekdays_iso(cls, v: list[int] | None) -> list[int] | None:
        if v is not None and (not v or any(d not in range(1, 8) for d in v)):
            raise ValueError("weekdays: числа 1..7 (ISO, пн=1), минимум одно")
        return v

    @field_validator("window_end")
    @classmethod
    def window_order(cls, v: time, info) -> time:
        ws = info.data.get("window_start")
        if ws is not None and v <= ws:
            raise ValueError("window_end должен быть позже window_start")
        return v


class ScheduleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    route_id: int
    kind: ScheduleKind
    once_date: date | None
    weekdays: list[int] | None
    shift_kind: ShiftKind | None
    window_start: time
    window_end: time
    is_active: bool


# --- Shifts ---


class ShiftCreate(BaseModel):
    object_id: int
    guard_id: int
    starts_at: datetime
    ends_at: datetime

    @field_validator("ends_at")
    @classmethod
    def ends_after_start(cls, v: datetime, info) -> datetime:
        s = info.data.get("starts_at")
        if s is not None and v <= s:
            raise ValueError("ends_at должен быть позже starts_at")
        return v


class ShiftOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    object_id: int
    guard_id: int
    starts_at: datetime
    ends_at: datetime
    guard_full_name: str = ""
    object_name: str = ""


# --- Patrols (мониторинг) ---


class PatrolOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    object_id: int
    object_name: str = ""
    route_id: int
    route_name: str = ""
    patrol_date: date
    window_start: datetime
    window_end: datetime
    status: PatrolStatus
    started_by_id: int | None
    started_at: datetime | None
    finished_at: datetime | None
    checkpoints_total: int
    checkpoints_scanned: int


class DashboardRow(BaseModel):
    object_id: int
    object_name: str
    patrols_total: int
    in_progress: int
    completed: int
    missed: int
    partial: int
    planned: int
    violations: int


class DashboardOut(BaseModel):
    date: date
    rows: list[DashboardRow]


# --- Violations / notifications ---


class ViolationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    patrol_id: int
    kind: ViolationKind
    details: dict
    detected_at: datetime
    is_read: bool = False


# --- Audit ---


class AuditOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    action: str
    entity: str
    entity_id: int | None
    payload: dict
    created_at: datetime


# --- Mobile sync ---


class MobileCheckpoint(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    route_id: int
    order_num: int
    code: str
    name: str | None


class MobileRoute(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    object_id: int
    name: str


class MobilePatrol(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    object_id: int
    route_id: int
    patrol_date: date
    window_start: datetime
    window_end: datetime
    status: PatrolStatus
    checkpoints_total: int
    checkpoints_scanned: int


class MobileShift(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    object_id: int
    starts_at: datetime
    ends_at: datetime


class MobileSyncOut(BaseModel):
    routes: list[MobileRoute]
    checkpoints: list[MobileCheckpoint]
    patrols: list[MobilePatrol]
    shifts: list[MobileShift]


class ScanIn(BaseModel):
    client_uuid: str = Field(min_length=32, max_length=36)
    checkpoint_code: str = Field(min_length=3, max_length=32)
    scanned_at: datetime


class ScanBatchIn(BaseModel):
    scans: list[ScanIn] = Field(min_length=1, max_length=50)


class ScanResultOut(BaseModel):
    client_uuid: str
    result: str  # ScanResult
    message: str = ""


class PatrolStartOut(BaseModel):
    ok: bool
    patrol: MobilePatrol | None = None
    message: str = ""
