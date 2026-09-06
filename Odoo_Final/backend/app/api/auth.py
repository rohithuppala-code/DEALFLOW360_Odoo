from datetime import datetime
import re

from fastapi import APIRouter

from app.core.dependencies import CurrentUser, DbSession
from app.core.exceptions import AppError
from app.core.security import create_access_token, hash_password, verify_password
from app.models.customer import Customer, CustomerTier
from app.models.enums import CustomerStatus, UserRole
from app.models.user import User
from app.schemas.common import LoginIn, SignupIn
from app.services.access import ensure_customer_for_user, find_existing_customer, heal_customer_link
from app.services.serialize import user_public
from app.utils.response import ok

router = APIRouter()

SIGNUP_ROLES = {
    "SALES_REP": UserRole.SALES_REP,
    "SALES_MANAGER": UserRole.SALES_MANAGER,
    "FINANCE": UserRole.FINANCE,
    "ADMIN": UserRole.ADMIN,
    "CUSTOMER": UserRole.CUSTOMER,
}


def _token_payload(user: User) -> dict:
    return {"access_token": create_access_token({"sub": str(user.id), "role": user.role.value, "email": user.email, "name": user.name}), "token_type": "bearer", "user": user_public(user)}


@router.post("/signup")
def signup(payload: SignupIn, db: DbSession):
    email = payload.email.strip().lower()
    role_key = payload.role.strip().upper().replace(" ", "_")
    if role_key not in SIGNUP_ROLES:
        raise AppError("VALIDATION_ERROR", "Role must be Sales Rep, Sales Manager, Finance, Admin, or Customer.")
    if db.query(User).filter(User.email == email).first():
        raise AppError("CONFLICT", "An account with this email already exists.", 409)
    role = SIGNUP_ROLES[role_key]
    user = User(
        name=payload.name.strip(),
        email=email,
        password_hash=hash_password(payload.password),
        role=role,
        is_active=True,
    )
    db.add(user)
    db.flush()
    if role == UserRole.CUSTOMER:
        company = (payload.company or payload.name).strip()
        if not company:
            raise AppError("VALIDATION_ERROR", "Company name is required for customer accounts.")
        ensure_customer_for_user(db, user, company_name=company)
    db.commit()
    db.refresh(user)
    return ok(_token_payload(user), "Account created")


@router.post("/login")
def login(payload: LoginIn, db: DbSession):
    user = db.query(User).filter(User.email == payload.email.strip().lower()).first()
    if not user or not user.is_active or not verify_password(payload.password, user.password_hash):
        raise AppError("INVALID_CREDENTIALS", "Invalid email or password.", 401)
    user.last_login_at = datetime.utcnow()
    heal_customer_link(db, user)
    db.commit()
    db.refresh(user)
    return ok(_token_payload(user))


@router.get("/me")
def me(user: CurrentUser):
    return ok(user_public(user))


@router.post("/logout")
def logout(_: CurrentUser):
    return ok(None, "Signed out")
