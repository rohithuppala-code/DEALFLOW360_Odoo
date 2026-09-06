from fastapi import APIRouter, Query
from sqlalchemy.orm import joinedload, selectinload

from app.core.dependencies import CurrentUser, DbSession
from app.core.exceptions import AppError
from app.core.permissions import APPROVER_ROLES
from app.models.enums import ApprovalStatus, ApprovalStepStatus, RequestStatus, UserRole
from app.models.customer import Customer
from app.models.governance import ApprovalRequest, ApprovalStep
from app.models.negotiation import Negotiation, NegotiationRequest
from app.models.quote import Quote
from app.models.timeline import DealEvent
from app.schemas.common import CommentIn
from app.services.approval import approval_svc
from app.services.discount import line_policy_snapshot
from app.services.quote import load_quote, quote_engine
from app.services.serialize import quote_out
from app.utils.response import ok, page

router = APIRouter()


def _assert_approval_access(user, req: ApprovalRequest) -> None:
    if user.role in (UserRole.SALES_MANAGER, UserRole.FINANCE, UserRole.ADMIN):
        return
    if user.role == UserRole.SALES_REP and req.quote and req.quote.sales_rep_id == user.id:
        return
    if user.role == UserRole.SALES_REP and req.requested_by == user.id:
        return
    raise AppError("FORBIDDEN", "You cannot view this approval.", 403)


def _role_str(r) -> str:
    return getattr(r, "value", str(r)) if r is not None else ""


def _can_act(user, req: ApprovalRequest) -> bool:
    if getattr(req.status, "value", str(req.status)) != "PENDING":
        return False
    user_role = _role_str(getattr(user, "role", None))
    if user_role not in {"SALES_MANAGER", "FINANCE", "ADMIN"}:
        return False
    if user_role == "ADMIN":
        return True
    return any(
        _role_str(s.role) == user_role and _role_str(s.status) == "PENDING"
        for s in getattr(req, "steps", [])
    )


def _neg_requests(n: Negotiation | None) -> list[dict]:
    if not n:
        return []
    return [
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
        for r in n.requests
    ]


def _out(req: ApprovalRequest, user) -> dict:
    quote = req.quote
    return {
        "id": req.id,
        "status": req.status.value,
        "reason": req.reason,
        "risk_score": float(req.risk_score or 0),
        "is_reapproval": req.is_reapproval,
        "created_at": req.created_at.isoformat() if req.created_at else None,
        "can_act": _can_act(user, req),
        "requested_by": {"id": req.requester.id, "name": req.requester.name} if req.requester else None,
        "quote": {
            "id": quote.id,
            "quote_number": quote.quote_number,
            "title": quote.title,
            "customer": quote.customer.name if quote.customer else None,
            "tier": quote.customer.tier.name if quote.customer and quote.customer.tier else None,
            "sales_rep": quote.sales_rep.name if getattr(quote, "sales_rep", None) else None,
            "total": float(quote.total),
            "subtotal": float(quote.subtotal),
            "discount_total": float(quote.discount_total),
            "margin": float(quote.gross_margin_percent),
            "gross_profit": float(quote.gross_profit),
            "risk": float(quote.risk_score),
            "health": float(quote.deal_health_score),
            "status": quote.status.value,
            "approval_status": quote.approval_status.value,
        }
        if quote
        else None,
        "steps": [
            {
                "id": s.id,
                "role": s.role.value,
                "sequence": s.sequence,
                "status": s.status.value,
                "comment": s.comment,
                "acted_at": s.acted_at.isoformat() if s.acted_at else None,
                "approver": s.approver.name if s.approver else None,
            }
            for s in sorted(req.steps, key=lambda x: (x.sequence, x.id))
        ],
    }


def _load_request(db, approval_id: int) -> ApprovalRequest:
    req = (
        db.query(ApprovalRequest)
        .options(
            joinedload(ApprovalRequest.quote).joinedload(Quote.customer).joinedload(Customer.tier),
            joinedload(ApprovalRequest.quote).joinedload(Quote.sales_rep),
            joinedload(ApprovalRequest.requester),
            selectinload(ApprovalRequest.steps).joinedload(ApprovalStep.approver),
        )
        .filter(ApprovalRequest.id == approval_id)
        .first()
    )
    if not req:
        raise AppError("NOT_FOUND", "Approval not found.", 404)
    return req


@router.get("")
def list_approvals(
    db: DbSession,
    user: CurrentUser,
    status: str | None = "PENDING",
    page_num: int | None = Query(None, alias="page"),
    page_size: int | None = Query(None, alias="page_size"),
):
    q = db.query(ApprovalRequest).options(
        joinedload(ApprovalRequest.quote).joinedload(Quote.customer).joinedload(Customer.tier),
        joinedload(ApprovalRequest.quote).joinedload(Quote.sales_rep),
        joinedload(ApprovalRequest.requester),
        selectinload(ApprovalRequest.steps).joinedload(ApprovalStep.approver),
    )
    if status:
        q = q.filter(ApprovalRequest.status == status)
    if user.role == UserRole.SALES_REP:
        q = q.filter(
            (ApprovalRequest.requested_by == user.id) | (ApprovalRequest.quote.has(Quote.sales_rep_id == user.id))
        )
    elif user.role in (UserRole.SALES_MANAGER, UserRole.FINANCE):
        pass
    elif user.role != UserRole.ADMIN:
        raise AppError("FORBIDDEN", "Not allowed.", 403)
    rows = q.order_by(ApprovalRequest.created_at.asc()).all()
    if user.role in (UserRole.SALES_MANAGER, UserRole.FINANCE):
        filtered = []
        user_role_str = _role_str(user.role)
        for r in rows:
            has_my_role = any(_role_str(s.role) == user_role_str for s in getattr(r, "steps", []))
            is_active_now = any(
                _role_str(s.role) == user_role_str and _role_str(s.status) == "PENDING"
                for s in getattr(r, "steps", [])
            )
            if is_active_now:
                filtered.append(r)
            elif has_my_role and any(_role_str(s.status) == "PENDING" for s in getattr(r, "steps", [])):
                filtered.append(r)
            elif status and status != "PENDING":
                filtered.append(r)
        rows = filtered
    if page_num is not None or page_size is not None:
        p = page_num or 1
        ps = page_size or 20
        total = len(rows)
        start = (p - 1) * ps
        paged = rows[start : start + ps]
        return page([_out(r, user) for r in paged], total, p, ps)
    return ok([_out(r, user) for r in rows])


@router.get("/{approval_id}")
def get_approval(approval_id: int, db: DbSession, user: CurrentUser):
    req = _load_request(db, approval_id)
    _assert_approval_access(user, req)
    quote = load_quote(db, req.quote_id)
    intel = quote_engine.recalculate(db, quote)
    nego = (
        db.query(Negotiation)
        .options(selectinload(Negotiation.requests).joinedload(NegotiationRequest.category))
        .filter(Negotiation.quote_id == quote.id)
        .order_by(Negotiation.id.desc())
        .first()
    )
    pending_reqs = [r for r in (nego.requests if nego else []) if r.status == RequestStatus.PENDING]
    lines = line_policy_snapshot(db, quote, pending_reqs)
    events = (
        db.query(DealEvent)
        .options(joinedload(DealEvent.actor))
        .filter(DealEvent.quote_id == quote.id)
        .order_by(DealEvent.created_at.asc())
        .all()
    )
    discount = intel.get("discount") or {}
    blended = discount.get("blended") or {}
    data = _out(req, user)
    data["deal"] = quote_out(quote, user, extra={"intelligence": {
        "risk": intel.get("risk"),
        "health": intel.get("health"),
        "discount": discount,
        "approval_preview": intel.get("approval_preview"),
    }})
    data["lines"] = lines
    data["negotiation"] = {
        "id": nego.id if nego else None,
        "status": nego.status.value if nego else None,
        "comment": next((r.reason for r in pending_reqs if r.reason), None),
        "requests": _neg_requests(nego),
    }
    data["blended"] = {
        "deal_discount_percent": discount.get("deal_discount_percent"),
        "has_exceptions": blended.get("has_exceptions"),
        "exception_count": blended.get("exception_count"),
        "max_exception_points": blended.get("max_exception_points"),
        "risk_score": float(quote.risk_score or 0),
        "risk_level": (intel.get("risk") or {}).get("level"),
    }
    data["why"] = {
        "reasons": [r for r in (req.reason or "").split("; ") if r],
        "risk": float(quote.risk_score),
        "margin": float(quote.gross_margin_percent),
        "tier": quote.customer.tier.name if quote.customer and quote.customer.tier else None,
        "factors": [
            {"type": f.factor_type, "severity": float(f.severity), "message": f.message} for f in quote.risk_factors
        ],
    }
    data["timeline"] = [
        {
            "id": e.id,
            "type": e.event_type.value,
            "description": e.description,
            "created_at": e.created_at.isoformat() if e.created_at else None,
            "actor": e.actor.name if e.actor else None,
        }
        for e in events
    ]
    return ok(data)


@router.post("/{approval_id}/approve")
def approve(approval_id: int, payload: CommentIn, db: DbSession, user: CurrentUser):
    req = _load_request(db, approval_id)
    _assert_approval_access(user, req)
    if user.role not in APPROVER_ROLES:
        raise AppError("FORBIDDEN", "You cannot approve deals.", 403)
    req = approval_svc.act(db, req, user, "approve", payload.comment)
    db.commit()
    db.refresh(req)
    return ok(_out(_load_request(db, req.id), user), "Approved")


@router.post("/{approval_id}/reject")
def reject(approval_id: int, payload: CommentIn, db: DbSession, user: CurrentUser):
    req = _load_request(db, approval_id)
    _assert_approval_access(user, req)
    if user.role not in APPROVER_ROLES:
        raise AppError("FORBIDDEN", "You cannot reject deals.", 403)
    req = approval_svc.act(db, req, user, "reject", payload.comment)
    db.commit()
    return ok(_out(_load_request(db, req.id), user), "Rejected")


@router.post("/{approval_id}/request-changes")
def request_changes(approval_id: int, payload: CommentIn, db: DbSession, user: CurrentUser):
    req = _load_request(db, approval_id)
    _assert_approval_access(user, req)
    if user.role not in APPROVER_ROLES:
        raise AppError("FORBIDDEN", "You cannot return deals for revision.", 403)
    req = approval_svc.act(db, req, user, "request_changes", payload.comment)
    db.commit()
    return ok(_out(_load_request(db, req.id), user), "Changes requested")
