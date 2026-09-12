"""Аудит действий диспетчера."""
from sqlalchemy.orm import Session

from app.models import AuditLog


def audit_log(
    db: Session, user_id: int, action: str, entity: str, entity_id: int | None, payload: dict
) -> None:
    """Добавляет запись аудита (вызовcaller делает commit вместе с бизнес-мутацией)."""
    db.add(
        AuditLog(
            user_id=user_id,
            action=action,
            entity=entity,
            entity_id=entity_id,
            payload=payload,
        )
    )
