from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.enums import QuoteStatus
from app.models.quote import Quote, QuoteLine
from app.utils.money import D, ZERO, pct, safe_div


class AnomalyDetectionService:
    def detect_for_quote(self, db: Session, quote: Quote, deal_discount_percent: Decimal) -> list[dict]:
        anomalies: list[dict] = []
        anomalies.extend(self._rep_discount(db, quote, deal_discount_percent))
        anomalies.extend(self._deal_size(db, quote))
        anomalies.extend(self._customer_speed(db, quote))
        return anomalies

    def _rep_discount(self, db: Session, quote: Quote, deal_discount: Decimal) -> list[dict]:
        q = (
            db.query(func.avg(Quote.discount_total / func.nullif(Quote.subtotal, 0) * 100))
            .filter(
                Quote.sales_rep_id == quote.sales_rep_id,
                Quote.id != quote.id,
                Quote.status.in_(
                    [QuoteStatus.APPROVED, QuoteStatus.CONFIRMED, QuoteStatus.PENDING_APPROVAL, QuoteStatus.NEGOTIATING]
                ),
            )
            .scalar()
        )
        avg = D(q or 0)
        if avg <= 0:
            avg = D("8.5")
        delta = D(deal_discount) - avg
        if delta >= D("5"):
            return [
                {
                    "type": "REP_DISCOUNT_ANOMALY",
                    "severity": "HIGH" if delta >= 9 else "MEDIUM",
                    "message": (
                        f"Rep normally gives {float(avg):.1f}% discounts. "
                        f"Current deal: {float(deal_discount):.1f}%. Anomaly: +{float(delta):.1f}% above historical average."
                    ),
                    "rep_avg": float(pct(avg)),
                    "current": float(pct(deal_discount)),
                    "delta": float(pct(delta)),
                }
            ]
        return []

    def _deal_size(self, db: Session, quote: Quote) -> list[dict]:
        avg = (
            db.query(func.avg(Quote.total))
            .filter(Quote.customer_id == quote.customer_id, Quote.id != quote.id, Quote.status != QuoteStatus.CANCELLED)
            .scalar()
        )
        avg_d = D(avg or 0)
        if avg_d <= 0:
            return []
        ratio = safe_div(D(quote.total), avg_d)
        if ratio >= D("2.5"):
            return [
                {
                    "type": "DEAL_SIZE_ANOMALY",
                    "severity": "MEDIUM",
                    "message": f"Deal value is {float(ratio):.1f}× this customer's historical average.",
                    "ratio": float(ratio),
                }
            ]
        return []

    def _customer_speed(self, db: Session, quote: Quote) -> list[dict]:
        if not quote.sent_to_customer_at or not quote.customer:
            return []
        from datetime import datetime

        days = (datetime.utcnow() - quote.sent_to_customer_at).days
        typical = float(quote.customer.avg_accept_days or 2)
        if days > typical * 2 and days >= 5:
            return [
                {
                    "type": "CUSTOMER_CYCLE_ANOMALY",
                    "severity": "MEDIUM",
                    "message": (
                        f"Customer normally accepts within {typical:.0f} days. "
                        f"Current negotiation cycle: {days} days."
                    ),
                    "days": days,
                    "typical": typical,
                }
            ]
        return []

    def detect_global(self, db: Session) -> list[dict]:
        """Dashboard-level anomalies across open deals."""
        open_status = [
            QuoteStatus.DRAFT,
            QuoteStatus.PENDING_APPROVAL,
            QuoteStatus.APPROVED,
            QuoteStatus.NEGOTIATING,
        ]
        quotes = db.query(Quote).filter(Quote.status.in_(open_status)).all()
        found: list[dict] = []
        for q in quotes:
            disc = safe_div(D(q.discount_total), D(q.subtotal)) * D(100)
            items = self.detect_for_quote(db, q, disc)
            for a in items:
                a["quote_id"] = q.id
                a["quote_number"] = q.quote_number
                found.append(a)
        return found[:20]
