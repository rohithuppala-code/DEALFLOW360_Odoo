from fastapi import APIRouter, Query
from sqlalchemy.orm import joinedload, selectinload

from app.core.dependencies import CurrentUser, DbSession
from app.core.exceptions import AppError
from app.core.permissions import is_customer
from app.models.customer import Customer, CustomerTier
from app.models.enums import CustomerStatus, UserRole
from app.schemas.common import CustomerIn
from app.services.access import customer_can_access_id, customer_scope_filter, portal_users_for_customer, reconcile_all_customer_users
from app.services.serialize import customer_out
from app.utils.pagination import paginate
from app.utils.response import ok, page

router = APIRouter()


@router.get("")
def list_customers(
    db: DbSession,
    user: CurrentUser,
    q: str | None = None,
    page_num: int = Query(1, alias="page"),
    page_size: int = 20,
    tier_id: int | None = None,
):
    reconcile_all_customer_users(db)
    query = db.query(Customer).options(joinedload(Customer.tier), selectinload(Customer.portal_users))
    if is_customer(user):
        query = query.filter(customer_scope_filter(Customer.id, db, user))
    if q:
        like = f"%{q}%"
        query = query.filter(Customer.name.ilike(like) | Customer.code.ilike(like) | Customer.email.ilike(like))
    if tier_id:
        query = query.filter(Customer.customer_tier_id == tier_id)
    query = query.order_by(Customer.name)
    items, total, p, ps = paginate(query, page_num, page_size)
    return page([customer_out(c) for c in items], total, p, ps)


@router.get("/tiers")
def tiers(db: DbSession, user: CurrentUser):
    rows = db.query(CustomerTier).order_by(CustomerTier.id).all()
    return ok(
        [
            {
                "id": t.id,
                "name": t.name,
                "description": t.description,
                "default_discount_limit": float(t.default_discount_limit),
                "risk_multiplier": float(t.risk_multiplier),
            }
            for t in rows
        ]
    )


@router.post("")
def create_customer(payload: CustomerIn, db: DbSession, user: CurrentUser):
    if user.role not in (UserRole.ADMIN, UserRole.SALES_MANAGER, UserRole.SALES_REP):
        raise AppError("FORBIDDEN", "Cannot create customers.", 403)
    c = Customer(
        name=payload.name,
        code=payload.code.upper(),
        email=payload.email,
        phone=payload.phone,
        industry=payload.industry,
        customer_tier_id=payload.customer_tier_id,
        credit_limit=payload.credit_limit,
        payment_terms=payload.payment_terms,
        city=payload.city,
        status=CustomerStatus(payload.status) if payload.status else CustomerStatus.ACTIVE,
        sales_rep_id=payload.sales_rep_id or user.id,
    )
    db.add(c)
    db.flush()
    portal_users_for_customer(db, c)
    db.commit()
    db.refresh(c)
    return ok(customer_out(c), "Customer created")


@router.get("/{customer_id}")
def get_customer(customer_id: int, db: DbSession, user: CurrentUser):
    c = db.get(Customer, customer_id)
    if not c:
        raise AppError("NOT_FOUND", "Customer not found.", 404)
    if is_customer(user) and not customer_can_access_id(db, user, c.id):
        raise AppError("FORBIDDEN", "Not allowed.", 403)
    return ok(customer_out(c))


@router.put("/{customer_id}")
def update_customer(customer_id: int, payload: CustomerIn, db: DbSession, user: CurrentUser):
    if user.role not in (UserRole.ADMIN, UserRole.SALES_MANAGER):
        raise AppError("FORBIDDEN", "Cannot update customers.", 403)
    c = db.get(Customer, customer_id)
    if not c:
        raise AppError("NOT_FOUND", "Customer not found.", 404)
    for field in ("name", "email", "phone", "industry", "customer_tier_id", "credit_limit", "payment_terms", "city"):
        setattr(c, field, getattr(payload, field))
    c.code = payload.code.upper()
    db.commit()
    db.refresh(c)
    return ok(customer_out(c))
