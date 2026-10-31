from typing import Any

from sqlalchemy.orm import Session

from app.models import AuditLog


def record(
    db: Session,
    *,
    actor_id: int | None,
    action: str,
    entity_type: str,
    entity_id: int | None,
    **details: Any,
) -> None:
    """Adds an audit row to the current transaction (committed with the business change)."""
    db.add(
        AuditLog(
            actor_user_id=actor_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            details={key: str(value) for key, value in details.items()} or None,
        )
    )
