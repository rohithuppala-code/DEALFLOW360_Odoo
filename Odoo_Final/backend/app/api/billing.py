from fastapi import APIRouter, Query
from sqlalchemy.orm import joinedload, selectinload

from app.core.dependencies import CurrentUser, DbSession
from app.core.exceptions import AppError
from app.core.permissions import BILLING_MUTATE_ROLES, BILLING_VIEW_ROLES, is_customer
from app.models.billing import Invoice, Payment, Subscription, SubscriptionPlan
from app.models.ops import Order
from app.schemas.common import PaymentIn, ProrationIn, SubscriptionCancelIn, SubscriptionChangeIn
from app.services.access import customer_can_access_id, customer_scope_filter
from app.services.billing import BillingService
from app.utils.pagination import paginate
from app.utils.response import ok, page

router = APIRouter()
svc = BillingService()


def _assert_billing_view(user):
    if is_customer(user) or user.role in BILLING_VIEW_ROLES:
        return
    raise AppError("FORBIDDEN", "Billing is limited to finance and operations.", 403)


def _assert_billing_mutate(user):
    if user.role not in BILLING_MUTATE_ROLES:
        raise AppError("FORBIDDEN", "Only finance can change billing records.", 403)


def _invoice_out(inv, hide_internal=False):
    one_time = sum(float(ln.amount) for ln in (inv.lines or []) if ln.billing_type.value == "ONE_TIME")
    recurring = sum(float(ln.amount) for ln in (inv.lines or []) if ln.billing_type.value == "RECURRING")
    proration = sum(float(ln.amount) for ln in (inv.lines or []) if ln.billing_type.value == "PRORATION")
    return {
        "id": inv.id,
        "invoice_number": inv.invoice_number,
        "status": inv.status.value,
        "invoice_date": str(inv.invoice_date),
        "due_date": str(inv.due_date),
        "subtotal": float(inv.subtotal),
        "discount": float(inv.discount),
        "tax": float(inv.tax),
        "total": float(inv.total),
        "balance_due": float(inv.balance_due),
        "one_time": one_time,
        "recurring": recurring,
        "proration": proration,
        "customer": {"id": inv.customer.id, "name": inv.customer.name} if inv.customer else None,
        "quote_id": inv.quote_id,
        "order_id": inv.order_id,
        "subscription_id": inv.subscription_id,
        "lines": [
            {
                "id": ln.id,
                "description": ln.description,
                "quantity": ln.quantity,
                "unit_price": float(ln.unit_price),
                "discount": float(ln.discount),
                "amount": float(ln.amount),
                "billing_type": ln.billing_type.value,
            }
            for ln in inv.lines
        ],
        "payments": [
            {
                "id": p.id,
                "amount": float(p.amount),
                "method": p.payment_method,
                "status": p.status.value,
                "paid_at": p.paid_at.isoformat() if p.paid_at else None,
            }
            for p in inv.payments
        ],
    }


def _sub_out(s) -> dict:
    return {
        "id": s.id,
        "status": s.status.value,
        "customer": s.customer.name if s.customer else None,
        "customer_id": s.customer_id,
        "plan": s.plan.name if s.plan else None,
        "plan_id": s.plan_id,
        "product": s.product.name if s.product else None,
        "interval": s.billing_interval.value,
        "quantity": s.quantity,
        "unit_price": float(s.unit_price),
        "discount_percent": float(s.discount_percent or 0),
        "mrr": float(s.mrr),
        "next_billing_date": str(s.next_billing_date) if s.next_billing_date else None,
        "start_date": str(s.start_date),
        "end_date": str(s.end_date) if s.end_date else None,
        "quote_id": s.quote_id,
        "schedule": svc.schedule(s),
    }


@router.get("/invoices")
def list_invoices(db: DbSession, user: CurrentUser, page_num: int = Query(1, alias="page"), page_size: int = 20):
    _assert_billing_view(user)
    q = (
        db.query(Invoice)
        .options(joinedload(Invoice.customer), selectinload(Invoice.lines), selectinload(Invoice.payments))
        .order_by(Invoice.id.desc())
    )
    if is_customer(user):
        q = q.filter(customer_scope_filter(Invoice.customer_id, db, user))
    items, total, p, ps = paginate(q, page_num, page_size)
    return page([_invoice_out(i) for i in items], total, p, ps)


@router.get("/invoices/{invoice_id}")
def get_invoice(invoice_id: int, db: DbSession, user: CurrentUser):
    _assert_billing_view(user)
    inv = (
        db.query(Invoice)
        .options(joinedload(Invoice.customer), selectinload(Invoice.lines), selectinload(Invoice.payments))
        .filter(Invoice.id == invoice_id)
        .first()
    )
    if not inv:
        raise AppError("NOT_FOUND", "Invoice not found.", 404)
    if is_customer(user) and not customer_can_access_id(db, user, inv.customer_id):
        raise AppError("FORBIDDEN", "Not allowed.", 403)
    return ok(_invoice_out(inv))


@router.post("/invoices/{invoice_id}/pay")
def pay_invoice(invoice_id: int, payload: PaymentIn, db: DbSession, user: CurrentUser):
    inv = db.get(Invoice, invoice_id)
    if not inv:
        raise AppError("NOT_FOUND", "Invoice not found.", 404)
    if is_customer(user):
        if not customer_can_access_id(db, user, inv.customer_id):
            raise AppError("FORBIDDEN", "Not allowed.", 403)
    elif user.role not in BILLING_MUTATE_ROLES:
        raise AppError("FORBIDDEN", "Only finance can record payments.", 403)
    svc.pay_invoice(db, inv, payload.amount, payload.payment_method, user.id)
    db.commit()
    db.refresh(inv)
    return ok(_invoice_out(inv), "Payment recorded")


@router.get("/subscriptions/plans")
def list_plans(db: DbSession, user: CurrentUser):
    _assert_billing_view(user)
    if is_customer(user):
        raise AppError("FORBIDDEN", "Not allowed.", 403)
    rows = db.query(SubscriptionPlan).order_by(SubscriptionPlan.name).all()
    return ok(
        [
            {
                "id": p.id,
                "name": p.name,
                "interval": p.billing_interval.value,
                "price": float(p.price),
                "setup_fee": float(p.setup_fee or 0),
                "trial_days": p.trial_days,
            }
            for p in rows
        ]
    )


@router.get("/payments")
def list_payments(
    db: DbSession,
    user: CurrentUser,
    page_num: int | None = Query(None, alias="page"),
    page_size: int | None = Query(None, alias="page_size"),
    q: str | None = None,
):
    _assert_billing_view(user)
    query = (
        db.query(Payment)
        .join(Payment.invoice)
        .options(joinedload(Payment.invoice).joinedload(Invoice.customer))
        .order_by(Payment.id.desc())
    )
    if is_customer(user):
        query = query.filter(customer_scope_filter(Invoice.customer_id, db, user))
    if q:
        query = query.filter(Invoice.invoice_number.ilike(f"%{q}%"))
    if page_num is not None or page_size is not None:
        items, total, p, ps = paginate(query, page_num or 1, page_size or 20)
        return page(
            [
                {
                    "id": pm.id,
                    "invoice_id": pm.invoice_id,
                    "invoice_number": pm.invoice.invoice_number if pm.invoice else None,
                    "customer": pm.invoice.customer.name if pm.invoice and pm.invoice.customer else None,
                    "amount": float(pm.amount),
                    "method": pm.payment_method,
                    "status": pm.status.value,
                    "paid_at": pm.paid_at.isoformat() if pm.paid_at else None,
                    "reference": pm.reference,
                }
                for pm in items
            ],
            total,
            p,
            ps,
        )
    rows = query.all()
    return ok(
        [
            {
                "id": pm.id,
                "invoice_id": pm.invoice_id,
                "invoice_number": pm.invoice.invoice_number if pm.invoice else None,
                "customer": pm.invoice.customer.name if pm.invoice and pm.invoice.customer else None,
                "amount": float(pm.amount),
                "method": pm.payment_method,
                "status": pm.status.value,
                "paid_at": pm.paid_at.isoformat() if pm.paid_at else None,
                "reference": pm.reference,
            }
            for pm in rows
        ]
    )


@router.get("/subscriptions")
def list_subs(
    db: DbSession,
    user: CurrentUser,
    page_num: int | None = Query(None, alias="page"),
    page_size: int | None = Query(None, alias="page_size"),
):
    _assert_billing_view(user)
    q = (
        db.query(Subscription)
        .options(joinedload(Subscription.customer), joinedload(Subscription.plan), joinedload(Subscription.product))
        .order_by(Subscription.id.desc())
    )
    if is_customer(user):
        q = q.filter(customer_scope_filter(Subscription.customer_id, db, user))
    if page_num is not None or page_size is not None:
        items, total, p, ps = paginate(q, page_num or 1, page_size or 20)
        return page([_sub_out(s) for s in items], total, p, ps)
    return ok([_sub_out(s) for s in q.all()])


@router.get("/subscriptions/{subscription_id}")
def get_sub(subscription_id: int, db: DbSession, user: CurrentUser):
    _assert_billing_view(user)
    s = db.get(Subscription, subscription_id)
    if not s:
        raise AppError("NOT_FOUND", "Subscription not found.", 404)
    if is_customer(user) and not customer_can_access_id(db, user, s.customer_id):
        raise AppError("FORBIDDEN", "Not allowed.", 403)
    return ok(_sub_out(s))


@router.post("/subscriptions/{subscription_id}/change")
def change_sub(subscription_id: int, payload: SubscriptionChangeIn, db: DbSession, user: CurrentUser):
    _assert_billing_mutate(user)
    s = db.get(Subscription, subscription_id)
    if not s:
        raise AppError("NOT_FOUND", "Subscription not found.", 404)
    plan = db.get(SubscriptionPlan, payload.plan_id) if payload.plan_id else None
    if payload.plan_id and not plan:
        raise AppError("NOT_FOUND", "Plan not found.", 404)
    result = svc.apply_subscription_change(
        db,
        s,
        new_plan=plan,
        quantity=payload.quantity,
        remaining_days=payload.remaining_days,
        reason=payload.reason,
        user_id=user.id,
    )
    db.commit()
    db.refresh(s)
    return ok({"subscription": _sub_out(s), **result}, "Subscription updated")


@router.post("/subscriptions/{subscription_id}/cancel")
def cancel_sub(subscription_id: int, payload: SubscriptionCancelIn, db: DbSession, user: CurrentUser):
    _assert_billing_mutate(user)
    s = db.get(Subscription, subscription_id)
    if not s:
        raise AppError("NOT_FOUND", "Subscription not found.", 404)
    result = svc.cancel_subscription(db, s, payload.remaining_days, payload.reason, user.id)
    db.commit()
    db.refresh(s)
    return ok({"subscription": _sub_out(s), **result}, "Subscription cancelled")


@router.get("/billing/schedules")
def billing_schedules(db: DbSession, user: CurrentUser):
    _assert_billing_view(user)
    if is_customer(user):
        raise AppError("FORBIDDEN", "Not allowed.", 403)
    rows = (
        db.query(Subscription)
        .options(joinedload(Subscription.customer), joinedload(Subscription.plan))
        .filter(Subscription.next_billing_date.isnot(None))
        .order_by(Subscription.next_billing_date.asc())
        .all()
    )
    return ok(
        [
            {
                "id": s.id,
                "customer": s.customer.name if s.customer else None,
                "plan": s.plan.name if s.plan else None,
                "status": s.status.value,
                "mrr": float(s.mrr),
                "next_billing_date": str(s.next_billing_date) if s.next_billing_date else None,
                "interval": s.billing_interval.value,
                "schedule": svc.schedule(s, 4),
            }
            for s in rows
            if s.status.value in ("ACTIVE", "TRIAL")
        ]
    )


@router.post("/billing/prorate")
def prorate(payload: ProrationIn, db: DbSession, user: CurrentUser):
    if user.role not in BILLING_VIEW_ROLES:
        raise AppError("FORBIDDEN", "Not allowed.", 403)
    return ok(svc.prorate(payload.old_price, payload.new_price, payload.remaining_days, payload.period_days))


@router.get("/orders")
def list_orders(db: DbSession, user: CurrentUser):
    _assert_billing_view(user)
    q = db.query(Order).options(joinedload(Order.customer)).order_by(Order.id.desc())
    if is_customer(user):
        q = q.filter(customer_scope_filter(Order.customer_id, db, user))
    rows = q.limit(50).all()
    return ok(
        [
            {
                "id": o.id,
                "order_number": o.order_number,
                "status": o.status.value,
                "total": float(o.total),
                "customer": o.customer.name if o.customer else None,
                "quote_id": o.quote_id,
                "confirmed_at": o.confirmed_at.isoformat() if o.confirmed_at else None,
            }
            for o in rows
        ]
    )
