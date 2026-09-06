from datetime import datetime

from fastapi import APIRouter, Query
from sqlalchemy.orm import joinedload, noload, selectinload

from app.core.dependencies import CurrentUser, DbSession
from app.core.exceptions import AppError
from app.core.permissions import APPROVER_ROLES, FULFILLMENT_ROLES, is_customer
from app.events.bus import event_bus, notify
from app.models.customer import Customer
from app.models.enums import ApprovalStatus, EventType, QuoteStatus, Severity, UserRole
from app.models.governance import ApprovalRequest, ApprovalStep
from app.models.quote import Quote
from app.schemas.common import (
    CommentIn,
    DiscountPatchIn,
    FulfillmentManualIn,
    QuoteCreateIn,
    QuoteLineIn,
    QuoteLinePatchIn,
    QuoteUpdateIn,
    SimulateIn,
)
from app.services.approval import approval_svc
from app.services.access import customer_scope_filter, portal_users_for_customer
from app.services.billing import BillingService
from app.services.copilot import DealCopilotService
from app.services.fulfillment import WarehouseAllocationService
from app.services.optimizer import DealOptimizerService, SimulationService
from app.services.order import OrderConfirmationService
from app.services.quote import assert_quote_access, load_quote, quote_engine
from app.services.recommendation import RecommendationService
from app.services.serialize import quote_out
from app.utils.pagination import paginate
from app.utils.response import ok, page

router = APIRouter()
copilot_svc = DealCopilotService()
rec_svc = RecommendationService()
opt_svc = DealOptimizerService()
sim_svc = SimulationService()
fulfill_svc = WarehouseAllocationService()
order_svc = OrderConfirmationService()
bill_svc = BillingService()


def _scope(db, user):
    q = db.query(Quote)
    if is_customer(user):
        q = q.filter(
            customer_scope_filter(Quote.customer_id, db, user),
            (Quote.sent_to_customer_at.isnot(None) | Quote.status.in_([QuoteStatus.APPROVED, QuoteStatus.NEGOTIATING, QuoteStatus.CONFIRMED]))
        )
        q = q.filter(Quote.status != QuoteStatus.CANCELLED)
    elif user.role == UserRole.SALES_REP:
        q = q.filter(Quote.sales_rep_id == user.id)
    return q


@router.get("")
def list_quotes(
    db: DbSession,
    user: CurrentUser,
    q: str | None = None,
    status: str | None = None,
    customer_id: int | None = None,
    risk: str | None = None,
    page_num: int = Query(1, alias="page"),
    page_size: int = 20,
    sort: str = "updated_at",
):
    query = _scope(db, user).options(
        joinedload(Quote.customer).joinedload(Customer.tier),
        joinedload(Quote.sales_rep),
        noload(Quote.lines),
        noload(Quote.risk_factors),
    )
    if q:
        like = f"%{q}%"
        query = query.filter(Quote.quote_number.ilike(like) | Quote.title.ilike(like))
    if status:
        query = query.filter(Quote.status == status)
    if customer_id:
        query = query.filter(Quote.customer_id == customer_id)
    if risk == "HIGH":
        query = query.filter(Quote.risk_score >= 60)
    if risk == "AT_RISK":
        query = query.filter(Quote.deal_health_score < 55)
    if sort == "total":
        query = query.order_by(Quote.total.desc())
    elif sort == "risk":
        query = query.order_by(Quote.risk_score.desc())
    else:
        query = query.order_by(Quote.updated_at.desc())
    items, total, p, ps = paginate(query, page_num, page_size)
    return page([quote_out(x, user, compact=True) for x in items], total, p, ps)


@router.post("")
def create_quote(payload: QuoteCreateIn, db: DbSession, user: CurrentUser):
    if is_customer(user):
        raise AppError("FORBIDDEN", "Customers cannot create quotes.", 403)
    quote = quote_engine.create(db, user, payload.model_dump())
    db.commit()
    db.refresh(quote)
    return ok(quote_out(load_quote(db, quote.id), user), "Quote created")


@router.post("/preview")
def preview_quote(payload: QuoteCreateIn, db: DbSession, user: CurrentUser):
    if is_customer(user):
        raise AppError("FORBIDDEN", "Not allowed.", 403)
    return ok(quote_engine.preview(db, payload.model_dump()))


@router.get("/{quote_id}")
def get_quote(quote_id: int, db: DbSession, user: CurrentUser):
    quote = load_quote(db, quote_id)
    assert_quote_access(user, quote)
    extra = {}
    if not is_customer(user):
        intel = quote_engine.recalculate(db, quote)
        extra["intelligence"] = {
            "risk": intel.get("risk"),
            "health": intel.get("health"),
            "discount": intel.get("discount"),
            "margin_guardian": intel.get("margin_guardian"),
            "approval_preview": intel.get("approval_preview"),
            "anomalies": intel.get("anomalies"),
        }
    extra["billing"] = bill_svc.quote_billing_summary(quote)
    return ok(quote_out(quote, user, extra))


@router.put("/{quote_id}")
def update_quote(quote_id: int, payload: QuoteUpdateIn, db: DbSession, user: CurrentUser):
    quote = load_quote(db, quote_id)
    assert_quote_access(user, quote)
    if is_customer(user):
        raise AppError("FORBIDDEN", "Use the negotiation endpoints to request changes.", 403)
    data = payload.model_dump(exclude_unset=True)
    quote = quote_engine.update(db, quote, user, data)
    db.commit()
    return ok(quote_out(load_quote(db, quote.id), user), "Quote updated")


@router.delete("/{quote_id}")
def delete_quote(quote_id: int, db: DbSession, user: CurrentUser):
    quote = load_quote(db, quote_id)
    assert_quote_access(user, quote)
    if quote.status != QuoteStatus.DRAFT:
        raise AppError("QUOTE_LOCKED", "Only draft quotes can be deleted.")
    quote.status = QuoteStatus.CANCELLED
    db.commit()
    return ok(None, "Quote cancelled")


@router.post("/{quote_id}/calculate")
def calculate(quote_id: int, db: DbSession, user: CurrentUser):
    quote = load_quote(db, quote_id)
    assert_quote_access(user, quote)
    intel = quote_engine.recalculate(db, quote)
    db.commit()
    return ok({"quote": quote_out(load_quote(db, quote.id), user), "intelligence": intel})


@router.post("/{quote_id}/lines")
def add_line(quote_id: int, payload: QuoteLineIn, db: DbSession, user: CurrentUser):
    quote = load_quote(db, quote_id)
    assert_quote_access(user, quote)
    quote = quote_engine.add_product(db, quote, user, payload.product_id, payload.quantity, payload.discount_percent)
    db.commit()
    return ok(quote_out(load_quote(db, quote.id), user))


@router.patch("/{quote_id}/lines/{line_id}")
def patch_line(quote_id: int, line_id: int, payload: QuoteLinePatchIn, db: DbSession, user: CurrentUser):
    quote = load_quote(db, quote_id)
    assert_quote_access(user, quote)
    if is_customer(user):
        raise AppError("FORBIDDEN", "Use the negotiation endpoints to request changes.", 403)
    quote = quote_engine.update_line(
        db,
        quote,
        user,
        line_id,
        quantity=payload.quantity,
        discount_percent=payload.discount_percent,
    )
    db.commit()
    intel = quote_engine._last_intel
    return ok({"quote": quote_out(load_quote(db, quote.id), user), "intelligence": intel})


@router.patch("/{quote_id}/lines/{line_id}/discount")
def patch_discount(quote_id: int, line_id: int, payload: DiscountPatchIn, db: DbSession, user: CurrentUser):
    quote = load_quote(db, quote_id)
    assert_quote_access(user, quote)
    quote = quote_engine.update_line_discount(db, quote, user, line_id, payload.discount_percent)
    db.commit()
    intel = quote_engine._last_intel
    return ok({"quote": quote_out(load_quote(db, quote.id), user), "intelligence": intel})


@router.post("/{quote_id}/submit")
def submit(quote_id: int, db: DbSession, user: CurrentUser):
    quote = load_quote(db, quote_id)
    assert_quote_access(user, quote)
    quote = quote_engine.submit(db, quote, user)
    db.commit()
    return ok(quote_out(load_quote(db, quote.id), user), "Submitted for approval")


@router.post("/{quote_id}/approve")
def approve_quote(quote_id: int, db: DbSession, user: CurrentUser, payload: CommentIn | None = None):
    quote = load_quote(db, quote_id)
    assert_quote_access(user, quote)
    if user.role not in APPROVER_ROLES:
        raise AppError("FORBIDDEN", "You do not have permission to approve quotes.", 403)
    req = (
        db.query(ApprovalRequest)
        .options(
            joinedload(ApprovalRequest.quote).joinedload(Quote.customer).joinedload(Customer.tier),
            joinedload(ApprovalRequest.quote).joinedload(Quote.sales_rep),
            joinedload(ApprovalRequest.requester),
            selectinload(ApprovalRequest.steps).joinedload(ApprovalStep.approver),
        )
        .filter(ApprovalRequest.quote_id == quote.id, ApprovalRequest.status == ApprovalStatus.PENDING)
        .order_by(ApprovalRequest.id.desc())
        .first()
    )
    if not req:
        if quote.status == QuoteStatus.PENDING_APPROVAL:
            quote.status = QuoteStatus.APPROVED
            quote.approval_status = ApprovalStatus.APPROVED
            if not quote.sent_to_customer_at:
                quote.sent_to_customer_at = datetime.utcnow()
            db.commit()
            return ok(quote_out(load_quote(db, quote.id), user), "Quote approved")
        raise AppError("NOT_FOUND", "No pending approval request found for this quote.", 404)
    comment = payload.comment if payload else None
    req = approval_svc.act(db, req, user, "approve", comment)
    db.commit()
    return ok(quote_out(load_quote(db, quote.id), user), "Quote approved")


@router.post("/{quote_id}/reject")
def reject_quote(quote_id: int, db: DbSession, user: CurrentUser, payload: CommentIn | None = None):
    quote = load_quote(db, quote_id)
    assert_quote_access(user, quote)
    if user.role not in APPROVER_ROLES:
        raise AppError("FORBIDDEN", "You do not have permission to reject quotes.", 403)
    req = (
        db.query(ApprovalRequest)
        .options(
            joinedload(ApprovalRequest.quote).joinedload(Quote.customer).joinedload(Customer.tier),
            joinedload(ApprovalRequest.quote).joinedload(Quote.sales_rep),
            joinedload(ApprovalRequest.requester),
            selectinload(ApprovalRequest.steps).joinedload(ApprovalStep.approver),
        )
        .filter(ApprovalRequest.quote_id == quote.id, ApprovalRequest.status == ApprovalStatus.PENDING)
        .order_by(ApprovalRequest.id.desc())
        .first()
    )
    if not req:
        if quote.status == QuoteStatus.PENDING_APPROVAL:
            quote.status = QuoteStatus.REJECTED
            quote.approval_status = ApprovalStatus.REJECTED
            db.commit()
            return ok(quote_out(load_quote(db, quote.id), user), "Quote rejected")
        raise AppError("NOT_FOUND", "No pending approval request found for this quote.", 404)
    comment = payload.comment if payload else None
    req = approval_svc.act(db, req, user, "reject", comment)
    db.commit()
    return ok(quote_out(load_quote(db, quote.id), user), "Quote rejected")


@router.post("/{quote_id}/request-changes")
def request_quote_changes(quote_id: int, db: DbSession, user: CurrentUser, payload: CommentIn | None = None):
    quote = load_quote(db, quote_id)
    assert_quote_access(user, quote)
    if user.role not in APPROVER_ROLES:
        raise AppError("FORBIDDEN", "You do not have permission to return quotes for revision.", 403)
    req = (
        db.query(ApprovalRequest)
        .options(
            joinedload(ApprovalRequest.quote).joinedload(Quote.customer).joinedload(Customer.tier),
            joinedload(ApprovalRequest.quote).joinedload(Quote.sales_rep),
            joinedload(ApprovalRequest.requester),
            selectinload(ApprovalRequest.steps).joinedload(ApprovalStep.approver),
        )
        .filter(ApprovalRequest.quote_id == quote.id, ApprovalRequest.status == ApprovalStatus.PENDING)
        .order_by(ApprovalRequest.id.desc())
        .first()
    )
    if not req:
        if quote.status == QuoteStatus.PENDING_APPROVAL:
            quote.status = QuoteStatus.DRAFT
            quote.approval_status = ApprovalStatus.CHANGES_REQUESTED
            db.commit()
            return ok(quote_out(load_quote(db, quote.id), user), "Changes requested")
        raise AppError("NOT_FOUND", "No pending approval request found for this quote.", 404)
    comment = payload.comment if payload else None
    req = approval_svc.act(db, req, user, "request_changes", comment)
    db.commit()
    return ok(quote_out(load_quote(db, quote.id), user), "Changes requested")


@router.post("/{quote_id}/send")
def send_to_customer(quote_id: int, db: DbSession, user: CurrentUser):
    quote = load_quote(db, quote_id)
    assert_quote_access(user, quote)
    if quote.status == QuoteStatus.DRAFT:
        quote = quote_engine.submit(db, quote, user)
    if quote.status not in (QuoteStatus.APPROVED, QuoteStatus.NEGOTIATING):
        raise AppError("NOT_APPROVED", "Approve the quote before sending it to the customer.")
    quote.sent_to_customer_at = datetime.utcnow()
    event_bus.publish(
        EventType.QUOTE_SENT,
        {"quote_id": quote.id, "actor_id": user.id, "description": f"Quote sent to {quote.customer.name}"},
        db,
    )
    if quote.customer:
        for pu in portal_users_for_customer(db, quote.customer):
            notify(
                db,
                pu.id,
                "QUOTE_RECEIVED",
                f"New quote {quote.quote_number}",
                f"You have a new commercial offer totaling ₹{float(quote.total):,.0f}.",
                Severity.INFO,
                "quote",
                quote.id,
            )
    db.commit()
    return ok(quote_out(load_quote(db, quote.id), user), "Sent to customer")


@router.post("/{quote_id}/confirm")
def confirm(quote_id: int, db: DbSession, user: CurrentUser, admin_override: bool = False):
    quote = load_quote(db, quote_id)
    assert_quote_access(user, quote)
    order = order_svc.confirm(db, quote, user, admin_override=admin_override)
    db.commit()
    return ok(
        {"order_id": order.id, "order_number": order.order_number, "quote": quote_out(load_quote(db, quote.id), user)},
        "Order confirmed",
    )


@router.get("/{quote_id}/risk")
def get_risk(quote_id: int, db: DbSession, user: CurrentUser):
    quote = load_quote(db, quote_id)
    assert_quote_access(user, quote)
    if is_customer(user):
        raise AppError("FORBIDDEN", "Not available.", 403)
    intel = quote_engine.recalculate(db, quote)
    return ok(intel["risk"])


@router.post("/{quote_id}/risk/recalculate")
def recalc_risk(quote_id: int, db: DbSession, user: CurrentUser):
    quote = load_quote(db, quote_id)
    assert_quote_access(user, quote)
    intel = quote_engine.recalculate(db, quote)
    db.commit()
    return ok(intel["risk"])


@router.get("/{quote_id}/copilot")
def copilot(quote_id: int, db: DbSession, user: CurrentUser):
    quote = load_quote(db, quote_id)
    assert_quote_access(user, quote)
    if is_customer(user):
        raise AppError("FORBIDDEN", "Not available.", 403)
    intel = quote_engine.recalculate(db, quote)
    fulfillment = fulfill_svc.optimize(db, quote, quote.customer, persist_recommended=True)
    data = copilot_svc.build(db, quote, intel, fulfillment)
    db.commit()
    return ok(data)


@router.get("/{quote_id}/health")
def health(quote_id: int, db: DbSession, user: CurrentUser):
    quote = load_quote(db, quote_id)
    assert_quote_access(user, quote)
    if is_customer(user):
        raise AppError("FORBIDDEN", "Not available.", 403)
    intel = quote_engine.recalculate(db, quote)
    return ok(intel["health"])


@router.get("/{quote_id}/recommendations")
def recommendations(quote_id: int, db: DbSession, user: CurrentUser):
    quote = load_quote(db, quote_id)
    assert_quote_access(user, quote)
    if is_customer(user):
        raise AppError("FORBIDDEN", "Not available.", 403)
    return ok(rec_svc.for_quote(db, quote))


@router.post("/{quote_id}/recommendations/{recommendation_id}/apply")
def apply_rec(quote_id: int, recommendation_id: int, db: DbSession, user: CurrentUser):
    quote = load_quote(db, quote_id)
    assert_quote_access(user, quote)
    recs = rec_svc.for_quote(db, quote)
    rec = next((r for r in recs if r["id"] == recommendation_id), None)
    if not rec:
        raise AppError("NOT_FOUND", "Recommendation not found.", 404)
    quote = quote_engine.add_product(db, quote, user, rec["recommended_product_id"], 1, 0)
    db.commit()
    return ok({"quote": quote_out(load_quote(db, quote.id), user), "impact": rec})


@router.post("/{quote_id}/optimize")
def optimize(quote_id: int, db: DbSession, user: CurrentUser):
    quote = load_quote(db, quote_id)
    assert_quote_access(user, quote)
    result = opt_svc.optimize(db, quote)
    db.commit()
    return ok(result)


@router.post("/{quote_id}/optimize/apply")
def apply_optimize(quote_id: int, db: DbSession, user: CurrentUser):
    quote = load_quote(db, quote_id)
    assert_quote_access(user, quote)
    result = opt_svc.optimize(db, quote)
    quote = opt_svc.apply(db, quote, user, result)
    db.commit()
    return ok(quote_out(load_quote(db, quote.id), user), "Optimization applied")


@router.post("/{quote_id}/simulate")
def simulate(quote_id: int, payload: SimulateIn, db: DbSession, user: CurrentUser):
    quote = load_quote(db, quote_id)
    assert_quote_access(user, quote)
    scenario = payload.model_dump()
    scenario["add_product_ids"] = list(scenario.get("add_product_ids") or [])
    scenario["line_discounts"] = scenario.get("line_discounts") or {}
    scenario["line_quantities"] = scenario.get("line_quantities") or {}
    if payload.add_premium_support:
        from app.models.catalog import Product

        support = db.query(Product).filter(Product.sku == "SUP-PREM").first()
        if support and support.id not in scenario["add_product_ids"]:
            scenario["add_product_ids"].append(support.id)
    result = sim_svc.run(db, quote, user, scenario)
    db.commit()
    return ok(result)


@router.post("/{quote_id}/simulate/{simulation_id}/apply")
def apply_sim(quote_id: int, simulation_id: int, db: DbSession, user: CurrentUser):
    quote = load_quote(db, quote_id)
    assert_quote_access(user, quote)
    quote = sim_svc.apply(db, quote, user, simulation_id)
    db.commit()
    return ok(quote_out(load_quote(db, quote.id), user), "Scenario applied")


@router.get("/{quote_id}/fulfillment")
def get_fulfillment(quote_id: int, db: DbSession, user: CurrentUser):
    quote = load_quote(db, quote_id)
    assert_quote_access(user, quote)
    if is_customer(user):
        raise AppError("FORBIDDEN", "Not available.", 403)
    current = fulfill_svc.current_plan(db, quote, quote.customer)
    rec_allocs = [a for a in quote.allocations if a.is_recommended]
    recommended = None
    if rec_allocs:
        recommended = fulfill_svc._summarize(db, quote, quote.customer, rec_allocs, recommended=True, persist=False)
    return ok(
        {
            "current": current,
            "recommended": recommended,
            "availability": fulfill_svc.availability(db, quote),
        }
    )


@router.post("/{quote_id}/fulfillment/optimize")
def opt_fulfillment(quote_id: int, db: DbSession, user: CurrentUser):
    quote = load_quote(db, quote_id)
    assert_quote_access(user, quote)
    result = fulfill_svc.optimize(db, quote, quote.customer, persist_recommended=True)
    db.commit()
    return ok(result)


@router.post("/{quote_id}/fulfillment/allocate")
def manual_fulfillment(quote_id: int, payload: FulfillmentManualIn, db: DbSession, user: CurrentUser):
    quote = load_quote(db, quote_id)
    assert_quote_access(user, quote)
    if user.role not in FULFILLMENT_ROLES:
        raise AppError("FORBIDDEN", "Only finance or operations can override warehouse allocation.", 403)
    summary = fulfill_svc.manual_allocate(
        db,
        quote,
        quote.customer,
        [row.model_dump() for row in payload.allocations],
    )
    quote_engine.recalculate(db, quote)
    event_bus.publish(
        EventType.WAREHOUSE_OPTIMIZED,
        {
            "quote_id": quote.id,
            "actor_id": user.id,
            "description": f"Manual warehouse allocation · {summary['shipments']} shipments · backorder {summary['backorder_qty']}",
        },
        db,
    )
    db.commit()
    return ok({"current": summary, "quote": quote_out(load_quote(db, quote.id), user)}, "Allocation saved")


@router.post("/{quote_id}/fulfillment/consolidate")
def consolidate_fulfillment(quote_id: int, db: DbSession, user: CurrentUser):
    quote = load_quote(db, quote_id)
    assert_quote_access(user, quote)
    if user.role not in FULFILLMENT_ROLES:
        raise AppError("FORBIDDEN", "Only finance or operations can consolidate backorders.", 403)
    summary = fulfill_svc.consolidate_backorders(db, quote, quote.customer)
    quote_engine.recalculate(db, quote)
    event_bus.publish(
        EventType.WAREHOUSE_OPTIMIZED,
        {
            "quote_id": quote.id,
            "actor_id": user.id,
            "description": f"Backorders consolidated against current stock · remaining {summary['backorder_qty']}",
        },
        db,
    )
    db.commit()
    return ok({"current": summary, "quote": quote_out(load_quote(db, quote.id), user)}, "Backorders rechecked")


@router.post("/{quote_id}/fulfillment/apply")
def apply_fulfillment(quote_id: int, db: DbSession, user: CurrentUser):
    quote = load_quote(db, quote_id)
    assert_quote_access(user, quote)
    fulfill_svc.optimize(db, quote, quote.customer, persist_recommended=True)
    applied = fulfill_svc.apply_recommended(db, quote)
    quote_engine.recalculate(db, quote)
    from app.models.enums import EventType as ET

    event_bus.publish(
        ET.WAREHOUSE_OPTIMIZED,
        {
            "quote_id": quote.id,
            "actor_id": user.id,
            "description": f"Fulfillment plan applied · {applied['shipments']} shipments",
        },
        db,
    )
    db.commit()
    return ok({"applied": applied, "quote": quote_out(load_quote(db, quote.id), user)})


@router.get("/{quote_id}/billing")
def quote_billing(quote_id: int, db: DbSession, user: CurrentUser):
    quote = load_quote(db, quote_id)
    assert_quote_access(user, quote)
    return ok(bill_svc.quote_billing_summary(quote))


@router.get("/{quote_id}/timeline")
def timeline(quote_id: int, db: DbSession, user: CurrentUser):
    quote = load_quote(db, quote_id)
    assert_quote_access(user, quote)
    events = sorted(quote.events, key=lambda e: e.created_at)
    hide_types = set()
    if is_customer(user):
        hide_types = {
            "RISK_RECALCULATED",
            "APPROVAL_REQUESTED",
            "APPROVAL_APPROVED",
            "APPROVAL_REJECTED",
            "WAREHOUSE_OPTIMIZED",
            "ANOMALY_DETECTED",
        }
    return ok(
        [
            {
                "id": e.id,
                "type": e.event_type.value,
                "description": e.description,
                "created_at": e.created_at.isoformat(),
                "actor": e.actor.name if e.actor and not is_customer(user) else None,
                "metadata": None if is_customer(user) else e.metadata_json,
            }
            for e in events
            if e.event_type.value not in hide_types
        ]
    )


@router.get("/{quote_id}/negotiation")
def get_negotiation(quote_id: int, db: DbSession, user: CurrentUser):
    quote = load_quote(db, quote_id)
    assert_quote_access(user, quote)
    from app.models.negotiation import Negotiation, NegotiationRequest

    n = (
        db.query(Negotiation)
        .options(selectinload(Negotiation.requests).joinedload(NegotiationRequest.category))
        .filter(Negotiation.quote_id == quote.id)
        .order_by(Negotiation.id.desc())
        .first()
    )
    if not n:
        return ok(None)
    return ok(_neg_out(n, user))


@router.post("/{quote_id}/negotiation")
def start_negotiation(quote_id: int, payload: dict, db: DbSession, user: CurrentUser):
    from app.schemas.common import NegotiationIn
    from app.services.negotiation import NegotiationIntelligenceService

    quote = load_quote(db, quote_id)
    assert_quote_access(user, quote)
    data = NegotiationIn(**payload)
    result = NegotiationIntelligenceService().request_change(db, quote, user, data.model_dump())
    db.commit()
    return ok(
        {
            "analysis": result["analysis"],
            "negotiation": _neg_out(result["negotiation"], user),
            "quote": quote_out(load_quote(db, quote.id), user),
        }
    )


def _parse_category(old_value: str | None) -> tuple[str | None, str | None]:
    if not old_value:
        return None, None
    if "|" in old_value:
        name, current = old_value.split("|", 1)
        return name, current
    return None, old_value


def _neg_out(n, user):
    hide = is_customer(user)
    return {
        "id": n.id,
        "status": n.status.value,
        "quote_id": n.quote_id,
        "last_counteroffer": n.last_counteroffer_json,
        "requests": [
            {
                "id": r.id,
                "type": r.request_type.value,
                "request_type": r.request_type.value,
                "category_id": r.category_id,
                "category": (r.category.name if getattr(r, "category", None) else _parse_category(r.old_value)[0]),
                "current_discount": _parse_category(r.old_value)[1],
                "old_value": r.old_value,
                "requested_value": r.requested_value,
                "reason": r.reason,
                "status": r.status.value,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "counteroffer": r.counteroffer_json,
                "margin_impact": None if hide else float(r.margin_impact or 0),
                "risk_impact": None if hide else float(r.risk_impact or 0),
                "exception_percent": float(r.exception_percent or 0) if not hide else None,
            }
            for r in n.requests
        ],
    }
