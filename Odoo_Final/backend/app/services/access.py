"""Customer-portal ownership helpers.

A portal user must only see quotes (and related records) for their own
customer account. Signup can create a second Customer row with the same
email as an account the sales rep already quoted, so we resolve every
matching customer id — never an open query.
"""

from decimal import Decimal
import re
from sqlalchemy import func, or_, false
from sqlalchemy.orm import Session

from app.models.customer import Customer, CustomerTier
from app.models.enums import CustomerStatus, UserRole
from app.models.user import User


def normalize_email(email: str | None) -> str:
    return (email or "").strip().lower()


def portal_customer_ids(db: Session, user: User) -> list[int]:
    """Customer ids this portal login may access. Empty → no access."""
    if user is None or user.role != UserRole.CUSTOMER:
        return []
    ids: set[int] = set()
    if user.customer_id:
        ids.add(int(user.customer_id))
    email = normalize_email(user.email)
    if email:
        for (cid,) in db.query(Customer.id).filter(func.lower(Customer.email) == email).all():
            if cid:
                ids.add(int(cid))
    uname = getattr(user, "name", None)
    if uname:
        name = uname.strip().lower()
        if name:
            for (cid,) in db.query(Customer.id).filter(func.lower(Customer.name) == name).all():
                if cid:
                    ids.add(int(cid))
    return sorted(ids)


def customer_scope_filter(column, db: Session, user: User):
    """SQLAlchemy filter that never falls open when the user has no account."""
    ids = portal_customer_ids(db, user)
    if not ids:
        return false()
    return column.in_(ids)


def customer_can_access_id(db: Session, user: User, customer_id: int | None) -> bool:
    if not customer_id:
        return False
    return int(customer_id) in set(portal_customer_ids(db, user))


def customer_owns_quote(user: User, quote) -> bool:
    if user is None or quote is None:
        return False
    if user.customer_id and quote.customer_id == user.customer_id:
        return True
    uemail = normalize_email(user.email)
    customer = getattr(quote, "customer", None)
    cemail = normalize_email(getattr(customer, "email", None))
    if uemail and cemail and uemail == cemail:
        return True
    uname = (getattr(user, "name", None) or "").strip().lower()
    cname = normalize_email(getattr(customer, "name", None)) if customer else ""
    return bool(uname and cname and uname == cname)


def find_existing_customer(db: Session, *, email: str, company: str | None = None) -> Customer | None:
    """Reuse a sales-created (or seeded) customer instead of duplicating it."""
    email_n = normalize_email(email)
    if email_n:
        hit = (
            db.query(Customer)
            .filter(func.lower(Customer.email) == email_n)
            .order_by(Customer.id.asc())
            .first()
        )
        if hit:
            return hit
    name = (company or "").strip()
    if not name:
        return None
    matches = db.query(Customer).filter(func.lower(Customer.name) == name.lower()).all()
    if len(matches) != 1:
        return None
    existing = matches[0]
    portal = (
        db.query(User)
        .filter(User.customer_id == existing.id, User.role == UserRole.CUSTOMER)
        .all()
    )
    if not portal:
        return existing
    if email_n and any(normalize_email(u.email) == email_n for u in portal):
        return existing
    return None


def ensure_customer_for_user(db: Session, user: User, company_name: str | None = None) -> Customer | None:
    """Ensure a User with role == CUSTOMER is always linked to a valid Customer record."""
    if user is None or user.role != UserRole.CUSTOMER:
        return None

    if user.customer_id:
        c = db.get(Customer, user.customer_id)
        if c:
            return c

    # 1. Try to find existing customer by email or company name
    email = normalize_email(user.email)
    comp = (company_name or getattr(user, "name", "") or "").strip()
    found = find_existing_customer(db, email=email, company=comp)
    if found:
        user.customer_id = found.id
        return found

    # 2. If not found, automatically create a valid Customer record
    tier = db.query(CustomerTier).order_by(CustomerTier.id.asc()).first()
    if not tier:
        tier = CustomerTier(name="Standard", description="Default", default_discount_limit=Decimal(10), risk_multiplier=Decimal(1))
        db.add(tier)
        db.flush()

    sales_rep = (
        db.query(User)
        .filter(User.role == UserRole.SALES_REP, User.is_active.is_(True))
        .order_by(User.id.asc())
        .first()
    )
    sales_rep_id = sales_rep.id if sales_rep else None

    cname = comp or (getattr(user, "name", "") or "").strip() or "Customer"
    base = re.sub(r"[^A-Z0-9]", "", cname.upper())[:12] or "CUST"
    code = base
    n = 1
    while db.query(Customer).filter(Customer.code == code).first():
        n += 1
        code = f"{base}{n}"

    customer = Customer(
        name=cname,
        code=code,
        email=user.email,
        customer_tier_id=tier.id,
        status=CustomerStatus.ACTIVE,
        sales_rep_id=sales_rep_id,
        credit_limit=Decimal(1000000),
        payment_terms=30,
    )
    db.add(customer)
    db.flush()
    user.customer_id = customer.id
    return customer


def heal_customer_link(db: Session, user: User) -> None:
    """Attach a portal user that has no customer_id to a matching Customer row or ensure one exists."""
    if user is None or user.role != UserRole.CUSTOMER:
        return
    ensure_customer_for_user(db, user)


def reconcile_all_customer_users(db: Session) -> int:
    """Find any User with role == CUSTOMER and no valid Customer link, and heal it.
    Also ensures active customers have a sales rep assigned.
    """
    orphans = (
        db.query(User)
        .filter(User.role == UserRole.CUSTOMER)
        .all()
    )
    healed = 0
    for u in orphans:
        if not u.customer_id or not db.get(Customer, u.customer_id):
            ensure_customer_for_user(db, u)
            healed += 1

    unassigned = db.query(Customer).filter(Customer.sales_rep_id.is_(None)).all()
    if unassigned:
        default_rep = (
            db.query(User)
            .filter(User.role == UserRole.SALES_REP, User.is_active.is_(True))
            .order_by(User.id.asc())
            .first()
        )
        if default_rep:
            for c in unassigned:
                c.sales_rep_id = default_rep.id
                healed += 1

    if healed:
        db.commit()
    return healed


def portal_users_for_customer(db: Session, customer: Customer) -> list[User]:
    """Portal logins that belong to this customer (id or email)."""
    if customer is None:
        return []
    email = normalize_email(customer.email)
    conds = [User.customer_id == customer.id]
    if email:
        conds.append(func.lower(User.email) == email)
    rows = (
        db.query(User)
        .filter(User.role == UserRole.CUSTOMER, User.is_active.is_(True), or_(*conds))
        .all()
    )
    for u in rows:
        if u.customer_id is None:
            u.customer_id = customer.id
    return rows
