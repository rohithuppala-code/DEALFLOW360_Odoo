from fastapi import APIRouter, Depends

from app.core.dependencies import DbSession, require_roles
from app.models.enums import UserRole
from app.models.user import User
from app.services.serialize import user_public
from app.utils.response import ok

router = APIRouter()


@router.get("")
def list_users(db: DbSession, user: User = Depends(require_roles(UserRole.ADMIN, UserRole.SALES_MANAGER))):
    rows = db.query(User).order_by(User.name).all()
    return ok([user_public(u) for u in rows])
