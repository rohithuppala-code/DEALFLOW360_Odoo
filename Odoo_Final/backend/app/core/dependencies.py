from typing import Annotated

from fastapi import Depends, Header
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import InvalidTokenError
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.core.permissions import assert_role
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.enums import UserRole
from app.models.user import User

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    if creds is None or not creds.credentials:
        raise AppError("UNAUTHENTICATED", "Please sign in to continue.", 401)
    try:
        payload = decode_access_token(creds.credentials)
    except InvalidTokenError as exc:
        raise AppError("INVALID_TOKEN", "Session expired. Please sign in again.", 401) from exc
    user_id = payload.get("sub")
    if not user_id:
        raise AppError("INVALID_TOKEN", "Invalid session token.", 401)
    user = db.get(User, int(user_id))
    if not user or not user.is_active:
        raise AppError("UNAUTHENTICATED", "Account is inactive or not found.", 401)
    return user


def get_optional_user(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> User | None:
    if creds is None or not creds.credentials:
        return None
    try:
        return get_current_user(creds, db)
    except AppError:
        return None


def require_roles(*roles: UserRole):
    allowed = set(roles)

    def _inner(user: Annotated[User, Depends(get_current_user)]) -> User:
        assert_role(user, allowed)
        return user

    return _inner


def client_ip(x_forwarded_for: Annotated[str | None, Header()] = None) -> str | None:
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    return None


CurrentUser = Annotated[User, Depends(get_current_user)]
DbSession = Annotated[Session, Depends(get_db)]
