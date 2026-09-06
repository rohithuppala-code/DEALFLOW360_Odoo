from datetime import datetime

from sqlalchemy import case, func
from sqlalchemy.orm import Session, joinedload

from app.models.billing import Subscription
from app.models.catalog import Product
from app.models.enums import ApprovalStatus, QuoteStatus, ReservationStatus, SubscriptionStatus
from app.models.fulfillment import Backorder, InventoryReservation
from app.models.governance import ApprovalRequest
from app.models.quote import Quote, QuoteLine
from app.models.user import User
from app.utils.money import D, money, ZERO


class ReportService:
    def _quote_q(self, db: Session, filters: dict | None = None):
        q = db.query(Quote.id)
        f = filters or {}
        if f.get("from_date"):
            q = q.filter(Quote.created_at >= f["from_date"])
        if f.get("to_date"):
            q = q.filter(Quote.created_at <= f["to_date"])
        if f.get("sales_rep_id"):
            q = q.filter(Quote.sales_rep_id == int(f["sales_rep_id"]))
        if f.get("approval_status"):
            q = q.filter(Quote.approval_status == f["approval_status"])
        if f.get("status"):
            q = q.filter(Quote.status == f["status"])
        if f.get("product_id") or f.get("category_id"):
            q = q.join(QuoteLine, QuoteLine.quote_id == Quote.id)
            if f.get("product_id"):
                q = q.filter(QuoteLine.product_id == int(f["product_id"]))
            if f.get("category_id"):
                q = q.join(Product, Product.id == QuoteLine.product_id).filter(Product.category_id == int(f["category_id"]))
        ids = [i for (i,) in q.distinct().all()]
        if f.get("product_id") or f.get("category_id") or f.get("from_date") or f.get("to_date") or f.get("sales_rep_id") or f.get("approval_status") or f.get("status"):
            return db.query(Quote).filter(Quote.id.in_(ids or [-1]))
        return db.query(Quote)

    def sales(self, db: Session, filters: dict | None = None) -> dict:
        open_q = self._quote_q(db, filters).filter(Quote.status != QuoteStatus.CANCELLED)
        deals = open_q.with_entities(func.count(func.distinct(Quote.id))).scalar() or 0
        won_q = self._quote_q(db, filters).filter(Quote.status == QuoteStatus.CONFIRMED)
        won = won_q.with_entities(func.count(func.distinct(Quote.id))).scalar() or 0
        revenue = self._quote_q(db, filters).filter(Quote.status == QuoteStatus.CONFIRMED).with_entities(func.coalesce(func.sum(Quote.total), 0)).scalar()
        disc = self._quote_q(db, filters).filter(Quote.status != QuoteStatus.CANCELLED).with_entities(func.coalesce(func.sum(Quote.discount_total), 0)).scalar()
        sub = self._quote_q(db, filters).filter(Quote.status != QuoteStatus.CANCELLED).with_entities(func.coalesce(func.sum(Quote.subtotal), 0)).scalar()
        avg_size = (D(revenue) / won) if won else ZERO
        win_rate = won / deals * 100 if deals else 0
        return {
            "revenue": float(money(revenue)),
            "win_rate": round(win_rate, 1),
            "average_deal_size": float(money(avg_size)),
            "discount_average": float((D(disc) / D(sub) * 100) if sub else 0),
            "deals": int(deals),
            "won": int(won),
        }

    def margin(self, db: Session, filters: dict | None = None) -> dict:
        gp = self._quote_q(db, filters).filter(Quote.status != QuoteStatus.CANCELLED).with_entities(func.coalesce(func.sum(Quote.gross_profit), 0)).scalar()
        net = self._quote_q(db, filters).filter(Quote.status != QuoteStatus.CANCELLED).with_entities(func.coalesce(func.sum(Quote.subtotal - Quote.discount_total), 0)).scalar()
        bucket_expr = case(
            (Quote.gross_margin_percent < 12, "<12%"),
            (Quote.gross_margin_percent < 18, "12–18%"),
            (Quote.gross_margin_percent <= 25, "18–25%"),
            else_=">25%",
        )
        dist_rows = (
            self._quote_q(db, filters)
            .filter(Quote.status != QuoteStatus.CANCELLED)
            .with_entities(bucket_expr, func.count(func.distinct(Quote.id)))
            .group_by(bucket_expr)
            .all()
        )
        order = ["<12%", "12–18%", "18–25%", ">25%"]
        found = {k: 0 for k in order}
        for bucket, count in dist_rows:
            found[str(bucket)] = int(count)
        by_rep_rows = (
            self._quote_q(db, filters)
            .filter(Quote.status != QuoteStatus.CANCELLED)
            .join(User, User.id == Quote.sales_rep_id)
            .with_entities(
                User.name,
                func.coalesce(func.sum(Quote.gross_profit), 0),
                func.coalesce(func.sum(Quote.subtotal - Quote.discount_total), 0),
                func.count(func.distinct(Quote.id)),
            )
            .group_by(User.id, User.name)
            .all()
        )
        by_rep = []
        for name, profit, revenue, deals in by_rep_rows:
            rev = float(revenue or 0)
            prof = float(profit or 0)
            by_rep.append(
                {
                    "name": name,
                    "rep": name,
                    "profit": prof,
                    "revenue": rev,
                    "deals": int(deals),
                    "margin": round((prof / rev * 100) if rev else 0, 1),
                }
            )
        return {
            "gross_margin": round(float(D(gp) / D(net) * 100) if net else 0, 1),
            "gross_profit": float(money(gp)),
            "distribution": [{"bucket": k, "count": found[k]} for k in order],
            "by_rep": by_rep,
            "by_tier": [],
        }

    def discounts(self, db: Session, filters: dict | None = None) -> dict:
        exceptions = (
            self._quote_q(db, filters)
            .filter(Quote.status != QuoteStatus.CANCELLED, Quote.risk_score >= 50)
            .with_entities(func.count(func.distinct(Quote.id)))
            .scalar()
            or 0
        )
        rows_q = (
            self._quote_q(db, filters)
            .filter(Quote.status != QuoteStatus.CANCELLED)
            .join(User, User.id == Quote.sales_rep_id)
            .with_entities(
                User.name,
                func.coalesce(func.sum(Quote.discount_total), 0),
                func.coalesce(func.sum(Quote.subtotal), 0),
                func.coalesce(func.sum(Quote.gross_profit), 0),
            )
            .group_by(User.id, User.name)
            .all()
        )
        rows = []
        for name, discount, subtotal, profit in rows_q:
            sub = float(subtotal or 0)
            disc = float(discount or 0)
            avg = (disc / sub * 100) if sub else 0
            margin = (float(profit or 0) / (sub - disc) * 100) if (sub - disc) else 0
            rows.append({"rep": name, "avg_discount": round(avg, 1), "margin": round(margin, 1)})
        return {"exceptions": int(exceptions), "by_rep": rows}

    def approvals(self, db: Session, filters: dict | None = None) -> dict:
        q = db.query(ApprovalRequest)
        f = filters or {}
        if f.get("approval_status"):
            q = q.filter(ApprovalRequest.status == f["approval_status"])
        pending = q.filter(ApprovalRequest.status == ApprovalStatus.PENDING).with_entities(func.count(ApprovalRequest.id)).scalar() or 0
        approved = db.query(func.count(ApprovalRequest.id)).filter(ApprovalRequest.status == ApprovalStatus.APPROVED).scalar() or 0
        rejected = db.query(func.count(ApprovalRequest.id)).filter(ApprovalRequest.status == ApprovalStatus.REJECTED).scalar() or 0
        total_decided = int(approved) + int(rejected)
        return {
            "pending": int(pending),
            "approved": int(approved),
            "rejected": int(rejected),
            "approval_rate": round(int(approved) / total_decided * 100, 1) if total_decided else 0,
            "rejection_rate": round(int(rejected) / total_decided * 100, 1) if total_decided else 0,
            "average_hours": 0,
        }

    def fulfillment(self, db: Session, filters: dict | None = None) -> dict:
        shipments = self._quote_q(db, filters).filter(Quote.status != QuoteStatus.CANCELLED).with_entities(func.coalesce(func.sum(Quote.shipment_count), 0)).scalar() or 0
        shipping = self._quote_q(db, filters).filter(Quote.status != QuoteStatus.CANCELLED).with_entities(func.coalesce(func.sum(Quote.shipping_total), 0)).scalar()
        bos = db.query(func.coalesce(func.sum(Backorder.backorder_qty), 0)).scalar() or 0
        reserved = (
            db.query(func.coalesce(func.sum(InventoryReservation.quantity), 0))
            .filter(InventoryReservation.status == ReservationStatus.RESERVED)
            .scalar()
            or 0
        )
        return {
            "shipment_count": int(shipments),
            "shipping_cost": float(money(shipping)),
            "backorders": int(bos),
            "units_reserved": int(reserved),
        }

    def subscriptions(self, db: Session, filters: dict | None = None) -> dict:
        active_q = db.query(Subscription).filter(Subscription.status.in_([SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIAL]))
        cancelled = db.query(func.count(Subscription.id)).filter(Subscription.status == SubscriptionStatus.CANCELLED).scalar() or 0
        mrr = db.query(func.coalesce(func.sum(Subscription.mrr), 0)).filter(
            Subscription.status.in_([SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIAL])
        ).scalar()
        count = active_q.count()
        return {
            "mrr": float(money(mrr or 0)),
            "arr": float(money(D(mrr or 0) * 12)),
            "new_subscriptions": int(count),
            "churn": int(cancelled),
            "expansion": 0,
        }

    def table(self, db: Session, filters: dict | None = None) -> list[dict]:
        q = (
            self._quote_q(db, filters)
            .options(joinedload(Quote.customer), joinedload(Quote.sales_rep))
            .order_by(Quote.updated_at.desc())
        )
        rows = q.limit(500).all()
        return [
            {
                "quote_number": r.quote_number,
                "customer": r.customer.name if r.customer else "",
                "sales_rep": r.sales_rep.name if r.sales_rep else "",
                "status": r.status.value,
                "approval_status": r.approval_status.value,
                "total": float(r.total or 0),
                "margin": float(r.gross_margin_percent or 0),
                "discount": float(r.discount_total or 0),
                "created_at": r.created_at.isoformat() if r.created_at else "",
            }
            for r in rows
        ]
