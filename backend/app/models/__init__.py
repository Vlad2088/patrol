"""Модели SQLAlchemy 2 (declarative, Mapped/mapped_column)."""
from datetime import date, datetime, time
from enum import StrEnum as _StrEnum

from sqlalchemy import (
    ARRAY,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class UserRole(_StrEnum):
    DISPATCHER = "dispatcher"
    GUARD = "guard"


class ScheduleKind(_StrEnum):
    ONCE = "once"
    DAILY = "daily"
    WEEKLY = "weekly"
    SHIFT = "shift"


class ShiftKind(_StrEnum):
    DAY = "day"
    NIGHT = "night"


class PatrolStatus(_StrEnum):
    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    MISSED = "missed"
    PARTIAL = "partial"


class ViolationKind(_StrEnum):
    MISSED_PATROL = "missed_patrol"
    MISSED_POINTS = "missed_points"


class ScanResult(_StrEnum):
    """Итог серверной валидации одного скана (не хранится, коды ответа)."""
    ACCEPTED = "accepted"
    DUPLICATE = "duplicate"
    WRONG_CHECKPOINT = "wrong_checkpoint"
    OUT_OF_ORDER = "out_of_order"
    PATROL_CLOSED = "patrol_closed"
    OUT_OF_WINDOW = "out_of_window"  # принят, но вне окна (accepted с флагом)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    login: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role", native_enum=False), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    shifts: Mapped[list["Shift"]] = relationship(back_populates="guard")


class Object(Base):
    __tablename__ = "objects"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    address: Mapped[str | None] = mapped_column(String(500))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    routes: Mapped[list["Route"]] = relationship(back_populates="object")
    shifts: Mapped[list["Shift"]] = relationship(back_populates="object")
    patrols: Mapped[list["Patrol"]] = relationship(back_populates="object")


class Route(Base):
    __tablename__ = "routes"

    id: Mapped[int] = mapped_column(primary_key=True)
    object_id: Mapped[int] = mapped_column(
        ForeignKey("objects.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    object: Mapped[Object] = relationship(back_populates="routes")
    checkpoints: Mapped[list["Checkpoint"]] = relationship(
        back_populates="route",
        order_by="Checkpoint.order_num",
        cascade="all, delete-orphan",
    )
    schedules: Mapped[list["PatrolSchedule"]] = relationship(back_populates="route")


class Checkpoint(Base):
    __tablename__ = "checkpoints"
    __table_args__ = (
        UniqueConstraint("route_id", "order_num", name="uq_checkpoint_route_order"),
        UniqueConstraint("code", name="uq_checkpoint_code"),
        Index("ix_checkpoints_route", "route_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    route_id: Mapped[int] = mapped_column(
        ForeignKey("routes.id", ondelete="CASCADE"), nullable=False
    )
    order_num: Mapped[int] = mapped_column(Integer, nullable=False)
    code: Mapped[str] = mapped_column(String(32), nullable=False)  # R{route}-001
    name: Mapped[str | None] = mapped_column(String(255))

    route: Mapped[Route] = relationship(back_populates="checkpoints")


class PatrolSchedule(Base):
    """Расписание порождения обходов (шаблон)."""

    __tablename__ = "patrol_schedules"
    __table_args__ = (
        CheckConstraint(
            "kind != 'weekly' OR array_length(weekdays, 1) >= 1",
            name="ck_schedule_weekdays_not_empty",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    route_id: Mapped[int] = mapped_column(
        ForeignKey("routes.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[ScheduleKind] = mapped_column(
        Enum(ScheduleKind, name="schedule_kind", native_enum=False), nullable=False
    )
    # once: конкретная дата; weekly: дни недели 1..7 (ISO, пн=1)
    once_date: Mapped[date | None] = mapped_column(Date)
    weekdays: Mapped[list[int] | None] = mapped_column(ARRAY(Integer))
    shift_kind: Mapped[ShiftKind | None] = mapped_column(
        Enum(ShiftKind, name="shift_kind", native_enum=False)
    )
    window_start: Mapped[time] = mapped_column(nullable=False)  # локальное время
    window_end: Mapped[time] = mapped_column(nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    route: Mapped[Route] = relationship(back_populates="schedules")


class Shift(Base):
    """Смена: охранник закреплён за объектом на интервал."""

    __tablename__ = "shifts"
    __table_args__ = (Index("ix_shifts_object_starts", "object_id", "starts_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    object_id: Mapped[int] = mapped_column(
        ForeignKey("objects.id", ondelete="CASCADE"), nullable=False
    )
    guard_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    object: Mapped[Object] = relationship(back_populates="shifts")
    guard: Mapped[User] = relationship(back_populates="shifts")


class Patrol(Base):
    """Конкретный обход на дату (материализован из расписания)."""

    __tablename__ = "patrols"
    __table_args__ = (
        UniqueConstraint("schedule_id", "patrol_date", name="uq_patrol_schedule_date"),
        Index("ix_patrols_object_date", "object_id", "patrol_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    object_id: Mapped[int] = mapped_column(
        ForeignKey("objects.id", ondelete="CASCADE"), nullable=False
    )
    route_id: Mapped[int] = mapped_column(
        ForeignKey("routes.id", ondelete="RESTRICT"), nullable=False
    )
    schedule_id: Mapped[int | None] = mapped_column(
        ForeignKey("patrol_schedules.id", ondelete="SET NULL")
    )
    patrol_date: Mapped[date] = mapped_column(Date, nullable=False)
    window_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    window_end: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    status: Mapped[PatrolStatus] = mapped_column(
        Enum(PatrolStatus, name="patrol_status", native_enum=False),
        default=PatrolStatus.PLANNED,
        nullable=False,
    )
    started_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    checkpoints_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    checkpoints_scanned: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    object: Mapped[Object] = relationship(back_populates="patrols")
    scans: Mapped[list["ScanEvent"]] = relationship(back_populates="patrol")
    violations: Mapped[list["Violation"]] = relationship(back_populates="patrol")


class ScanEvent(Base):
    """Отметка прохождения точки (синхронизированная с устройства)."""

    __tablename__ = "scan_events"
    __table_args__ = (
        UniqueConstraint("client_uuid", name="uq_scan_client_uuid"),
        Index("ix_scans_patrol", "patrol_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    patrol_id: Mapped[int] = mapped_column(
        ForeignKey("patrols.id", ondelete="CASCADE"), nullable=False
    )
    checkpoint_id: Mapped[int] = mapped_column(
        ForeignKey("checkpoints.id", ondelete="RESTRICT"), nullable=False
    )
    guard_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    scanned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False  # время устройства
    )
    synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    client_uuid: Mapped[str] = mapped_column(String(36), nullable=False)
    out_of_window: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    patrol: Mapped[Patrol] = relationship(back_populates="scans")


class Violation(Base):
    __tablename__ = "violations"
    __table_args__ = (
        UniqueConstraint("patrol_id", "kind", name="uq_violation_patrol_kind"),
        Index("ix_violations_detected", "detected_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    patrol_id: Mapped[int] = mapped_column(
        ForeignKey("patrols.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[ViolationKind] = mapped_column(
        Enum(ViolationKind, name="violation_kind", native_enum=False), nullable=False
    )
    details: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    patrol: Mapped[Patrol] = relationship(back_populates="violations")


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (Index("ix_audit_created", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=False
    )
    action: Mapped[str] = mapped_column(String(32), nullable=False)  # create/update/delete
    entity: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[int | None] = mapped_column(Integer)
    payload: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
