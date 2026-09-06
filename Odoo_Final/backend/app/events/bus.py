from collections import defaultdict
from collections.abc import Callable
from typing import Any

from sqlalchemy.orm import Session

from app.models.enums import EventType, Severity
from app.models.timeline import DealEvent, Notification


Handler = Callable[[dict[str, Any], Session], None]


class EventBus:
    def __init__(self) -> None:
        self._handlers: dict[str, list[Handler]] = defaultdict(list)

    def subscribe(self, event_type: str, handler: Handler) -> None:
        self._handlers[event_type].append(handler)

    def publish(self, event_type: str, payload: dict[str, Any], db: Session) -> None:
        for handler in self._handlers.get(event_type, []):
            handler(payload, db)
        _write_timeline(event_type, payload, db)


event_bus = EventBus()


def _write_timeline(event_type: str, payload: dict[str, Any], db: Session) -> None:
    quote_id = payload.get("quote_id")
    if not quote_id:
        return
    try:
        et = EventType(event_type)
    except ValueError:
        return
    db.add(
        DealEvent(
            quote_id=quote_id,
            event_type=et,
            actor_id=payload.get("actor_id"),
            description=payload.get("description") or event_type.replace("_", " ").title(),
            metadata_json=payload.get("metadata"),
        )
    )


def notify(
    db: Session,
    user_id: int,
    ntype: str,
    title: str,
    message: str,
    severity: Severity = Severity.INFO,
    entity_type: str | None = None,
    entity_id: int | None = None,
) -> None:
    db.add(
        Notification(
            user_id=user_id,
            type=ntype,
            title=title,
            message=message,
            severity=severity,
            related_entity_type=entity_type,
            related_entity_id=entity_id,
        )
    )


def audit(
    db: Session,
    user_id: int | None,
    action: str,
    entity_type: str,
    entity_id: int | None,
    old_value: dict | None = None,
    new_value: dict | None = None,
    ip_address: str | None = None,
) -> None:
    from app.models.audit import AuditLog

    db.add(
        AuditLog(
            user_id=user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            old_value_json=old_value,
            new_value_json=new_value,
            ip_address=ip_address,
        )
    )
