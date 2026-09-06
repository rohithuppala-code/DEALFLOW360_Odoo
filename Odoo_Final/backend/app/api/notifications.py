from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from sqlalchemy import event as sa_event

from app.core.dependencies import CurrentUser, DbSession
from app.models.timeline import Notification
from app.utils.response import ok

router = APIRouter()


@router.get("")
def list_notes(db: DbSession, user: CurrentUser, unread_only: bool = False):
    q = db.query(Notification).filter(Notification.user_id == user.id)
    if unread_only:
        q = q.filter(Notification.is_read.is_(False))
    rows = q.order_by(Notification.created_at.desc()).limit(50).all()
    return ok(
        [
            {
                "id": n.id,
                "type": n.type,
                "title": n.title,
                "message": n.message,
                "severity": n.severity.value,
                "is_read": n.is_read,
                "related_entity_type": n.related_entity_type,
                "related_entity_id": n.related_entity_id,
                "created_at": n.created_at.isoformat() if n.created_at else None,
            }
            for n in rows
        ]
    )


@router.post("/{note_id}/read")
def mark_read(note_id: int, db: DbSession, user: CurrentUser):
    n = db.get(Notification, note_id)
    if n and n.user_id == user.id:
        n.is_read = True
        db.commit()
    return ok(True)


@router.post("/read-all")
def read_all(db: DbSession, user: CurrentUser):
    db.query(Notification).filter(Notification.user_id == user.id, Notification.is_read.is_(False)).update({"is_read": True})
    db.commit()
    return ok(True)
