from fastapi import APIRouter, Query
from sqlalchemy.orm import joinedload, selectinload

from app.core.dependencies import CurrentUser, DbSession
from app.core.exceptions import AppError
from app.core.permissions import APPROVER_ROLES, is_customer
from app.services.access import customer_scope_filter
from app.models.enums import ApprovalStatus, NegotiationStatus, QuoteStatus, RequestStatus, UserRole
from app.models.governance import ApprovalRequest
from app.models.negotiation import Negotiation, NegotiationRequest
from app.models.quote import Quote
from app.schemas.common import CommentIn, NegotiationIn
from app.services.negotiation import NegotiationIntelligenceService
from app.services.quote import assert_quote_access, load_quote
from app.services.serialize import quote_out
from app.utils.response import ok, page

router = APIRouter()
svc = NegotiationIntelligenceService()


def _inbox_item(n: Negotiation, approval_id: int | None = None) -> dict:
    quote = n.quote
    pending = [r for r in n.requests if r.status == RequestStatus.PENDING]
    exceeds = any(float(r.exception_percent or 0) > 0 for r in pending)
    return {
        "id": n.id,
        "status": n.status.value,
        "quote_id": n.quote_id,
        "quote_number": quote.quote_number if quote else None,
        "customer": quote.customer.name if quote and quote.customer else None,
        "sales_rep": quote.sales_rep.name if quote and getattr(quote, "sales_rep", None) else None,
        "total": float(quote.total) if quote else 0,
        "quote_status": quote.status.value if quote else None,
        "approval_id": approval_id,
        "exceeds_policy": exceeds,
        "comment": next((r.reason for r in pending if r.reason), None),
        "requests": [
            {
                "id": r.id,
                "request_type": r.request_type.value,
                "category": r.category.name if r.category else (r.old_value.split("|")[0] if r.old_value and "|" in r.old_value else None),
                "current_discount": r.old_value.split("|")[1] if r.old_value and "|" in r.old_value else r.old_value,
                "requested_value": r.requested_value,
                "reason": r.reason,
                "status": r.status.value,
                "exception_percent": float(r.exception_percent or 0),
            }
            for r in pending
        ],
    }


@router.get("")
def list_negotiations(
    db: DbSession,
    user: CurrentUser,
    status: str | None = "open",
    page_num: int | None = Query(None, alias="page"),
    page_size: int | None = Query(None, alias="page_size"),
):
    q = (
        db.query(Negotiation)
        .options(
            joinedload(Negotiation.quote).joinedload(Quote.customer),
            joinedload(Negotiation.quote).joinedload(Quote.sales_rep),
            selectinload(Negotiation.requests).joinedload(NegotiationRequest.category),
        )
        .order_by(Negotiation.updated_at.desc())
    )
    if is_customer(user):
        q = q.filter(customer_scope_filter(Negotiation.customer_id, db, user))
    elif user.role == UserRole.SALES_REP:
        q = q.filter(Negotiation.quote.has(Quote.sales_rep_id == user.id))
    elif user.role not in (UserRole.SALES_MANAGER, UserRole.FINANCE, UserRole.ADMIN):
        raise AppError("FORBIDDEN", "Not allowed.", 403)
    if status == "open":
        q = q.filter(Negotiation.status.in_([NegotiationStatus.OPEN, NegotiationStatus.COUNTERED]))
    rows = q.all()
    pending_by_quote = {}
    quote_ids = [n.quote_id for n in rows]
    if quote_ids:
        for req in (
            db.query(ApprovalRequest)
            .filter(ApprovalRequest.quote_id.in_(quote_ids), ApprovalRequest.status == ApprovalStatus.PENDING)
            .all()
        ):
            pending_by_quote.setdefault(req.quote_id, req.id)
    items = [
        _inbox_item(n, pending_by_quote.get(n.quote_id))
        for n in rows
        if any(r.status == RequestStatus.PENDING for r in n.requests) or n.status in (NegotiationStatus.OPEN, NegotiationStatus.COUNTERED)
    ]
    if page_num is not None or page_size is not None:
        p = page_num or 1
        ps = page_size or 20
        total = len(items)
        start = (p - 1) * ps
        paged = items[start : start + ps]
        return page(paged, total, p, ps)
    return ok(items)


@router.post("/{negotiation_id}/request")
def add_request(negotiation_id: int, payload: NegotiationIn, db: DbSession, user: CurrentUser):
    n = db.get(Negotiation, negotiation_id)
    if not n:
        raise AppError("NOT_FOUND", "Negotiation not found.", 404)
    quote = load_quote(db, n.quote_id)
    assert_quote_access(user, quote)
    result = svc.request_change(db, quote, user, payload.model_dump())
    db.commit()
    return ok({"analysis": result["analysis"], "quote": quote_out(load_quote(db, quote.id), user)})


@router.post("/{negotiation_id}/accept")
def accept(negotiation_id: int, db: DbSession, user: CurrentUser):
    n = db.get(Negotiation, negotiation_id)
    if not n:
        raise AppError("NOT_FOUND", "Negotiation not found.", 404)
    quote = load_quote(db, n.quote_id)
    assert_quote_access(user, quote)
    quote = svc.accept_counteroffer(db, quote, user)
    db.commit()
    return ok(quote_out(load_quote(db, quote.id), user), "Counteroffer accepted")


@router.post("/{negotiation_id}/accept-quote")
def accept_quote(negotiation_id: int, db: DbSession, user: CurrentUser):
    n = db.get(Negotiation, negotiation_id)
    if not n:
        raise AppError("NOT_FOUND", "Negotiation not found.", 404)
    quote = load_quote(db, n.quote_id)
    assert_quote_access(user, quote)
    quote = svc.accept_quote(db, quote, user)
    db.commit()
    return ok(quote_out(load_quote(db, quote.id), user), "Quote accepted")


@router.post("/{negotiation_id}/reject")
def reject(negotiation_id: int, payload: CommentIn, db: DbSession, user: CurrentUser):
    n = db.get(Negotiation, negotiation_id)
    if not n:
        raise AppError("NOT_FOUND", "Negotiation not found.", 404)
    quote = load_quote(db, n.quote_id)
    assert_quote_access(user, quote)
    if user.role in APPROVER_ROLES:
        if not (payload.comment or "").strip():
            raise AppError("VALIDATION_ERROR", "Please add a reason.")
        svc.reject_pending(db, quote, user, payload.comment)
    else:
        pending = next((r for r in n.requests if r.status.value == "PENDING"), None)
        if pending:
            svc.reject_request(db, quote, user, pending.id, payload.comment)
    db.commit()
    return ok(quote_out(load_quote(db, quote.id), user), "Rejected")


@router.post("/{negotiation_id}/approve-changes")
def approve_changes(negotiation_id: int, payload: CommentIn, db: DbSession, user: CurrentUser):
    n = db.get(Negotiation, negotiation_id)
    if not n:
        raise AppError("NOT_FOUND", "Negotiation not found.", 404)
    quote = load_quote(db, n.quote_id)
    assert_quote_access(user, quote)
    if user.role not in APPROVER_ROLES and user.id != quote.sales_rep_id:
        raise AppError("FORBIDDEN", "Only the assigned sales rep, manager, or finance approver can accept requested terms.", 403)
    applied = svc.apply_pending_requests(db, quote, user)
    from app.services.approval import approval_svc

    ctx = quote_engine_ctx(quote)
    evaluation = approval_svc.evaluate(db, quote, ctx)
    pending = (
        db.query(ApprovalRequest)
        .filter(ApprovalRequest.quote_id == quote.id, ApprovalRequest.status == ApprovalStatus.PENDING)
        .first()
    )
    if evaluation["required"] and not pending:
        approval_svc.submit(db, quote, user, ctx)
    elif not evaluation["required"] and quote.status == QuoteStatus.NEGOTIATING:
        quote.status = QuoteStatus.APPROVED
        quote.approval_status = ApprovalStatus.APPROVED
    db.commit()
    return ok(quote_out(load_quote(db, quote.id), user), "Requested terms accepted" if applied else "No pending requests")


@router.post("/{negotiation_id}/return-to-rep")
def return_to_rep(negotiation_id: int, payload: CommentIn, db: DbSession, user: CurrentUser):
    if user.role not in APPROVER_ROLES:
        raise AppError("FORBIDDEN", "Only a sales manager can return a deal for revision.", 403)
    n = db.get(Negotiation, negotiation_id)
    if not n:
        raise AppError("NOT_FOUND", "Negotiation not found.", 404)
    quote = load_quote(db, n.quote_id)
    assert_quote_access(user, quote)
    svc.return_to_rep(db, quote, user, payload.comment)
    db.commit()
    return ok(quote_out(load_quote(db, quote.id), user), "Returned to sales rep")


def quote_engine_ctx(quote):
    from app.services.quote import quote_engine

    return quote_engine._approval_context(quote, getattr(quote_engine, "_last_intel", None))
