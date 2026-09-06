from datetime import date, datetime

from sqlalchemy import case, func, or_
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models.billing import Invoice, Subscription
from app.models.enums import (
    ApprovalStatus,
    InvoiceStatus,
    QuoteStatus,
    SubscriptionStatus,
    UserRole,
)
from app.models.fulfillment import Backorder, Inventory, Warehouse
from app.models.governance import ApprovalRequest
from app.models.negotiation import Negotiation
from app.models.ops import Order
from app.models.quote import Quote
from app.models.timeline import DealEvent
from app.models.user import User
from app.services.anomaly import AnomalyDetectionService
from app.utils.money import D, money, ZERO


OPEN = [
    QuoteStatus.DRAFT,
    QuoteStatus.PENDING_APPROVAL,
    QuoteStatus.APPROVED,
    QuoteStatus.NEGOTIATING,
]
COUNTED = OPEN + [QuoteStatus.CONFIRMED]


class DashboardService:
    def summary(self, db: Session) -> dict:
        pipeline = db.query(func.coalesce(func.sum(Quote.total), 0)).filter(Quote.status.in_(OPEN)).scalar()
        confirmed_rev = (
            db.query(func.coalesce(func.sum(Quote.total), 0)).filter(Quote.status == QuoteStatus.CONFIRMED).scalar()
        )
        active = db.query(func.count(Quote.id)).filter(Quote.status.in_(OPEN)).scalar() or 0
        at_risk = (
            db.query(func.count(Quote.id))
            .filter(Quote.status.in_(OPEN), or_(Quote.risk_score >= 60, Quote.deal_health_score < 55))
            .scalar()
            or 0
        )
        pending = (
            db.query(func.count(ApprovalRequest.id)).filter(ApprovalRequest.status == ApprovalStatus.PENDING).scalar() or 0
        )
        negotiations = (
            db.query(func.count(Negotiation.id)).filter(Negotiation.status.in_(["OPEN", "COUNTERED"])).scalar() or 0
        )
        backorders = db.query(func.count(Backorder.id)).filter(Backorder.backorder_qty > 0).scalar() or 0
        gp = db.query(func.coalesce(func.sum(Quote.gross_profit), 0)).filter(Quote.status.in_(COUNTED)).scalar()
        net = (
            db.query(func.coalesce(func.sum(Quote.subtotal - Quote.discount_total), 0))
            .filter(Quote.status.in_(COUNTED))
            .scalar()
        )
        margin = float((D(gp) / D(net) * 100) if net else 0)
        mrr = (
            db.query(func.coalesce(func.sum(Subscription.mrr), 0))
            .filter(Subscription.status.in_([SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIAL]))
            .scalar()
        )
        expected = (
            db.query(func.coalesce(func.sum(Quote.total), 0))
            .filter(
                Quote.status.in_(OPEN),
                Quote.approval_status.in_([ApprovalStatus.APPROVED, ApprovalStatus.NOT_REQUIRED]),
            )
            .scalar()
        )
        return {
            "pipeline": float(money(pipeline)),
            "confirmed_revenue": float(money(confirmed_rev)),
            "expected_revenue": float(money(expected)),
            "active_deals": int(active),
            "at_risk": int(at_risk),
            "pending_approvals": int(pending),
            "gross_margin": round(margin, 1),
            "negotiations": int(negotiations),
            "backorders": int(backorders),
            "mrr": float(money(mrr or 0)),
            "arr": float(money(D(mrr or 0) * 12)),
            "orders": db.query(func.count(Order.id)).scalar() or 0,
        }

    def pipeline(self, db: Session) -> dict:
        rows = (
            db.query(Quote.status, func.count(Quote.id), func.coalesce(func.sum(Quote.total), 0))
            .group_by(Quote.status)
            .all()
        )
        mapping = {s.value: {"count": 0, "value": 0.0} for s in QuoteStatus}
        for status, count, total in rows:
            mapping[status.value] = {"count": int(count), "value": float(total)}
        stages = [
            {"key": "DRAFT", "label": "Draft", **mapping["DRAFT"]},
            {"key": "PENDING_APPROVAL", "label": "Pending Approval", **mapping["PENDING_APPROVAL"]},
            {"key": "APPROVED", "label": "Approved", **mapping["APPROVED"]},
            {"key": "NEGOTIATING", "label": "Under Negotiation", **mapping["NEGOTIATING"]},
            {"key": "CONFIRMED", "label": "Confirmed", **mapping["CONFIRMED"]},
        ]
        return {"stages": stages}

    def margins(self, db: Session) -> dict:
        bucket_expr = case(
            (Quote.gross_margin_percent < 12, "<12%"),
            (Quote.gross_margin_percent < 18, "12–18%"),
            (Quote.gross_margin_percent <= 25, "18–25%"),
            else_=">25%",
        )
        rows = (
            db.query(bucket_expr, func.count(Quote.id))
            .filter(Quote.status != QuoteStatus.CANCELLED)
            .group_by(bucket_expr)
            .all()
        )
        order = ["<12%", "12–18%", "18–25%", ">25%"]
        found = {k: 0 for k in order}
        for bucket, count in rows:
            found[str(bucket)] = int(count)
        by_rep_rows = (
            db.query(
                User.name,
                func.coalesce(func.sum(Quote.gross_profit), 0),
                func.coalesce(func.sum(Quote.subtotal - Quote.discount_total), 0),
                func.count(Quote.id),
            )
            .join(User, User.id == Quote.sales_rep_id)
            .filter(Quote.status != QuoteStatus.CANCELLED)
            .group_by(User.id, User.name)
            .all()
        )
        by_rep = []
        for name, profit, revenue, deals in by_rep_rows:
            rev = float(revenue or 0)
            prof = float(profit or 0)
            by_rep.append(
                {
                    "rep": name,
                    "profit": prof,
                    "revenue": rev,
                    "deals": int(deals),
                    "margin": round((prof / rev * 100) if rev else 0, 1),
                }
            )
        return {
            "distribution": [{"bucket": k, "count": found[k]} for k in order],
            "by_rep": by_rep,
        }

    def risks(self, db: Session) -> dict:
        open_q = (
            db.query(Quote)
            .options(joinedload(Quote.customer))
            .filter(Quote.status.in_(OPEN))
            .order_by(Quote.risk_score.desc())
            .limit(12)
            .all()
        )
        health = self.deal_health(db)
        return {
            "deals": [
                {
                    "id": q.id,
                    "quote_number": q.quote_number,
                    "customer": q.customer.name if q.customer else "",
                    "total": float(q.total),
                    "risk": float(q.risk_score),
                    "health": float(q.deal_health_score),
                    "margin": float(q.gross_margin_percent),
                    "status": q.status.value,
                }
                for q in open_q
            ],
            "anomalies": health["discount_anomalies"],
            "stalled": health["stalled"],
            "delivery_slippage": health["delivery_slippage"],
        }

    def deal_health(self, db: Session) -> dict:
        now = datetime.utcnow()
        today = date.today()
        open_q = (
            db.query(Quote)
            .options(joinedload(Quote.customer), selectinload(Quote.backorders), selectinload(Quote.approval_requests))
            .filter(Quote.status.in_(OPEN))
            .all()
        )
        stalled = []
        slippage = []
        for q in open_q:
            age = (now - q.created_at).days if q.created_at else 0
            pending_days = 0
            if q.approval_status == ApprovalStatus.PENDING and q.approval_requests:
                latest = max(q.approval_requests, key=lambda r: r.created_at or now)
                if latest.created_at:
                    pending_days = (now - latest.created_at).days
            reasons = []
            if age >= 10:
                reasons.append(f"Stalled {age} days in {q.status.value.replace('_', ' ').lower()}")
            if pending_days >= 2:
                reasons.append(f"Approval waiting {pending_days} days")
            if reasons:
                stalled.append(
                    {
                        "id": q.id,
                        "quote_id": q.id,
                        "quote_number": q.quote_number,
                        "customer": q.customer.name if q.customer else "",
                        "total": float(q.total),
                        "health": float(q.deal_health_score or 0),
                        "status": q.status.value,
                        "reason": "; ".join(reasons),
                        "href": f"/quotes/{q.id}",
                    }
                )
            backorder_qty = sum(int(b.backorder_qty or 0) for b in (q.backorders or []))
            late = bool(q.promised_delivery_date and q.promised_delivery_date < today)
            if backorder_qty > 0 or late:
                bits = []
                if backorder_qty > 0:
                    bits.append(f"{backorder_qty} units on backorder")
                if late:
                    bits.append(f"Promised {q.promised_delivery_date} has passed")
                slippage.append(
                    {
                        "id": q.id,
                        "quote_id": q.id,
                        "quote_number": q.quote_number,
                        "customer": q.customer.name if q.customer else "",
                        "total": float(q.total),
                        "status": q.status.value,
                        "reason": "; ".join(bits),
                        "href": f"/quotes/{q.id}",
                    }
                )
        anomalies = AnomalyDetectionService().detect_global(db)[:8]
        for a in anomalies:
            a["href"] = f"/quotes/{a.get('quote_id')}"
        stalled.sort(key=lambda x: x["health"])
        return {"stalled": stalled[:12], "discount_anomalies": anomalies, "delivery_slippage": slippage[:12]}

    def approvals(self, db: Session) -> dict:
        pending = (
            db.query(ApprovalRequest)
            .options(joinedload(ApprovalRequest.quote).joinedload(Quote.customer))
            .filter(ApprovalRequest.status == ApprovalStatus.PENDING)
            .order_by(ApprovalRequest.created_at.asc())
            .all()
        )
        aging = []
        now = datetime.utcnow()
        buckets = {"0–1d": 0, "2–3d": 0, "4–7d": 0, "7d+": 0}
        for r in pending:
            days = max((now - r.created_at).days, 0)
            if days <= 1:
                buckets["0–1d"] += 1
            elif days <= 3:
                buckets["2–3d"] += 1
            elif days <= 7:
                buckets["4–7d"] += 1
            else:
                buckets["7d+"] += 1
            aging.append(
                {
                    "id": r.id,
                    "quote_id": r.quote_id,
                    "quote_number": r.quote.quote_number if r.quote else None,
                    "customer": r.quote.customer.name if r.quote and r.quote.customer else None,
                    "total": float(r.quote.total) if r.quote else 0,
                    "risk": float(r.risk_score),
                    "age_days": days,
                    "reason": r.reason,
                    "is_reapproval": r.is_reapproval,
                }
            )
        return {"pending": aging, "aging": [{"bucket": k, "count": v} for k, v in buckets.items()]}

    def warehouses(self, db: Session) -> dict:
        rows = (
            db.query(
                Warehouse.id,
                Warehouse.name,
                Warehouse.city,
                func.coalesce(func.sum(Inventory.available_qty), 0),
                func.coalesce(func.sum(Inventory.reserved_qty), 0),
            )
            .outerjoin(Inventory, Inventory.warehouse_id == Warehouse.id)
            .group_by(Warehouse.id, Warehouse.name, Warehouse.city)
            .all()
        )
        out = []
        for wid, name, city, avail, reserved in rows:
            capacity = int(avail or 0) + int(reserved or 0)
            util = round(int(reserved or 0) / capacity * 100, 1) if capacity else 0
            out.append(
                {
                    "id": wid,
                    "name": name,
                    "city": city,
                    "available": int(avail or 0),
                    "reserved": int(reserved or 0),
                    "utilization": util,
                }
            )
        return {"warehouses": out}

    def subscriptions(self, db: Session) -> dict:
        active = (
            db.query(Subscription)
            .options(joinedload(Subscription.customer), joinedload(Subscription.plan))
            .filter(Subscription.status.in_([SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIAL]))
            .all()
        )
        mrr = sum((D(s.mrr) for s in active), ZERO)
        return {
            "mrr": float(money(mrr)),
            "arr": float(money(mrr * 12)),
            "count": len(active),
            "items": [
                {
                    "id": s.id,
                    "customer": s.customer.name if s.customer else "",
                    "plan": s.plan.name if s.plan else "",
                    "mrr": float(s.mrr),
                    "status": s.status.value,
                    "next_billing_date": str(s.next_billing_date) if s.next_billing_date else None,
                }
                for s in active
            ],
        }

    def activity(self, db: Session, limit: int = 12) -> list[dict]:
        events = db.query(DealEvent).order_by(DealEvent.created_at.desc()).limit(limit).all()
        return [
            {
                "id": e.id,
                "quote_id": e.quote_id,
                "type": e.event_type.value,
                "description": e.description,
                "created_at": e.created_at.isoformat(),
            }
            for e in events
        ]

    def actions(self, db: Session, user) -> list[dict]:
        items: list[dict] = []
        if user.role in (UserRole.SALES_MANAGER, UserRole.FINANCE, UserRole.ADMIN):
            pending = (
                db.query(ApprovalRequest)
                .options(joinedload(ApprovalRequest.quote).joinedload(Quote.customer), selectinload(ApprovalRequest.steps))
                .filter(ApprovalRequest.status == ApprovalStatus.PENDING)
                .order_by(ApprovalRequest.created_at.asc())
                .limit(6)
                .all()
            )
            for r in pending:
                if user.role != UserRole.ADMIN:
                    waiting = [s for s in r.steps if s.role == user.role and s.status.value == "PENDING"]
                    if not waiting:
                        continue
                qn = r.quote.quote_number if r.quote else "deal"
                items.append(
                    {
                        "id": f"appr-{r.id}",
                        "kind": "approval",
                        "title": f"Approve {qn}",
                        "detail": r.reason or "Policy review required",
                        "href": f"/approvals/{r.id}",
                        "tone": "warn",
                    }
                )

        scoped = db.query(Quote)
        if user.role == UserRole.SALES_REP:
            scoped = scoped.filter(Quote.sales_rep_id == user.id)

        if user.role in (UserRole.SALES_REP, UserRole.SALES_MANAGER, UserRole.ADMIN):
            for q in scoped.filter(Quote.status == QuoteStatus.DRAFT).order_by(Quote.updated_at.desc()).limit(3).all():
                items.append(
                    {
                        "id": f"draft-{q.id}",
                        "kind": "submit",
                        "title": f"Finish {q.quote_number}",
                        "detail": q.title or "Draft quote waiting to be submitted",
                        "href": f"/quotes/{q.id}",
                        "tone": "gold",
                    }
                )
            unsent = (
                scoped.filter(Quote.status == QuoteStatus.APPROVED, Quote.sent_to_customer_at.is_(None))
                .order_by(Quote.updated_at.desc())
                .limit(3)
                .all()
            )
            for q in unsent:
                items.append(
                    {
                        "id": f"send-{q.id}",
                        "kind": "send",
                        "title": f"Share {q.quote_number}",
                        "detail": "Approved internally — send the offer to the customer",
                        "href": f"/quotes/{q.id}",
                        "tone": "good",
                    }
                )
            for q in scoped.filter(Quote.status == QuoteStatus.NEGOTIATING).limit(3).all():
                items.append(
                    {
                        "id": f"nego-{q.id}",
                        "kind": "negotiate",
                        "title": f"Review {q.quote_number}",
                        "detail": "Customer requested a change",
                        "href": f"/quotes/{q.id}",
                        "tone": "info",
                    }
                )

        if user.role in (UserRole.FINANCE, UserRole.ADMIN):
            unpaid = (
                db.query(Invoice)
                .options(joinedload(Invoice.customer))
                .filter(
                    Invoice.balance_due > 0,
                    Invoice.status.in_([InvoiceStatus.ISSUED, InvoiceStatus.PARTIALLY_PAID, InvoiceStatus.OVERDUE]),
                )
                .order_by(Invoice.due_date.asc())
                .limit(3)
                .all()
            )
            for inv in unpaid:
                items.append(
                    {
                        "id": f"inv-{inv.id}",
                        "kind": "billing",
                        "title": f"Collect {inv.invoice_number}",
                        "detail": f"{inv.customer.name if inv.customer else 'Customer'} · balance due",
                        "href": "/billing",
                        "tone": "warn",
                    }
                )

        if user.role in (UserRole.OPERATIONS, UserRole.ADMIN, UserRole.FINANCE):
            count = db.query(func.count(Backorder.id)).filter(Backorder.backorder_qty > 0).scalar() or 0
            if count:
                items.append(
                    {
                        "id": "backorders",
                        "kind": "fulfill",
                        "title": f"{count} backorder line{'s' if count != 1 else ''}",
                        "detail": "Review warehouse stock and substitutes",
                        "href": "/fulfillment",
                        "tone": "warn",
                    }
                )

        return items[:8]
