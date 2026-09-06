from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.quote import Quote
from app.services.discount import evaluate_line_discount, load_discount_rules
from app.services.pricing import calculate_line, calculate_totals
from app.utils.money import D, money, pct


class DealCopilotService:
    def build(self, db: Session, quote: Quote, intel: dict, fulfillment: dict | None = None) -> dict:
        risk = intel.get("risk") or {}
        health = intel.get("health") or {}
        guardian = intel.get("margin_guardian") or {}
        approval = intel.get("approval_preview") or {}
        discount = intel.get("discount") or {}
        actions: list[dict] = []

        for ev in (discount.get("evaluations") or []):
            if float(ev.get("exception_percent") or 0) <= 0:
                continue
            suggested = float(ev["allowed_percent"]) + 4  # still a concession, inside blended comfort
            # cap at requested - 4 or allowed+4
            suggested = min(float(ev["requested_percent"]) - 4, max(float(ev["allowed_percent"]), suggested))
            suggested = max(suggested, float(ev["allowed_percent"]))
            impact = self._discount_impact(quote, ev["product_id"], suggested)
            actions.append(
                {
                    "id": f"reduce-discount-{ev['product_id']}",
                    "kind": "DISCOUNT",
                    "priority": "HIGH",
                    "title": f"Reduce {ev['product_name']} discount from {float(ev['requested_percent']):.0f}% → {suggested:.0f}%",
                    "reason": ev["message"] if "message" in ev else (
                        f"{ev['product_name']} exceeds {ev['rule_name']} by {float(ev['exception_percent']):.0f}%"
                    ),
                    "current_state": f"{float(ev['requested_percent']):.0f}% discount",
                    "suggested_change": f"{suggested:.0f}% discount",
                    "expected_impact": impact,
                    "confidence": 0.86,
                    "action": "APPLY_DISCOUNT",
                    "payload": {"product_id": ev["product_id"], "discount_percent": suggested},
                }
            )

        if guardian.get("recommendation"):
            rec = guardian["recommendation"]
            actions.append(
                {
                    "id": "margin-guardian",
                    "kind": "MARGIN",
                    "priority": "HIGH",
                    "title": rec["title"],
                    "reason": rec["recommended"],
                    "current_state": f"Customer saving ₹{guardian['customer_saving']:,.0f}",
                    "suggested_change": rec["recommended"],
                    "expected_impact": {
                        "profit_impact": guardian.get("profit_lost", 0) * 0.55,
                        "customer_value": rec.get("customer_value"),
                    },
                    "confidence": 0.8,
                    "action": "REVIEW_MARGIN",
                    "payload": {},
                }
            )

        from app.services.recommendation import RecommendationService

        recs = RecommendationService().for_quote(db, quote)
        for r in recs[:2]:
            actions.append(
                {
                    "id": f"add-rec-{r['id']}",
                    "kind": "UPSELL",
                    "priority": r["priority_label"],
                    "title": f"Add {r['product_name']}",
                    "reason": r["reason"],
                    "current_state": "Not on quote",
                    "suggested_change": f"Add {r['product_name']}",
                    "expected_impact": {
                        "revenue_impact": r["additional_revenue"],
                        "profit_impact": r["additional_profit"],
                        "margin_after": r["projected"]["margin"],
                    },
                    "confidence": r["confidence"] / 100,
                    "action": "ADD_PRODUCT",
                    "payload": {"product_id": r["recommended_product_id"], "quantity": 1},
                }
            )

        if fulfillment and fulfillment.get("recommended"):
            cur = fulfillment.get("current") or {}
            recf = fulfillment["recommended"]
            if recf.get("shipments", 99) < cur.get("shipments", 0) or recf.get("shipping_cost", 0) < cur.get("shipping_cost", 0):
                actions.append(
                    {
                        "id": "consolidate-fulfillment",
                        "kind": "FULFILLMENT",
                        "priority": "MEDIUM",
                        "title": f"Consolidate shipments from {cur.get('shipments')} → {recf.get('shipments')}",
                        "reason": recf.get("recommendation") or "Fewer warehouses lower shipping cost and delivery risk.",
                        "current_state": f"{cur.get('shipments')} shipments · ₹{cur.get('shipping_cost', 0):,.0f}",
                        "suggested_change": f"{recf.get('shipments')} shipments · ₹{recf.get('shipping_cost', 0):,.0f}",
                        "expected_impact": {
                            "shipping_savings": float(cur.get("shipping_cost", 0) - recf.get("shipping_cost", 0)),
                            "shipment_change": recf.get("shipments") - cur.get("shipments", 0),
                        },
                        "confidence": 0.9,
                        "action": "APPLY_FULFILLMENT",
                        "payload": {},
                    }
                )

        if approval.get("required"):
            actions.append(
                {
                    "id": "submit-approval",
                    "kind": "APPROVAL",
                    "priority": "HIGH",
                    "title": "Submit for " + " + ".join(approval.get("roles") or ["manager"]) + " approval",
                    "reason": "; ".join(approval.get("reasons") or ["Policy requires approval"]),
                    "current_state": quote.approval_status.value,
                    "suggested_change": "Request approval",
                    "expected_impact": {},
                    "confidence": 1,
                    "action": "SUBMIT_APPROVAL",
                    "payload": {},
                }
            )

        # headline statuses
        def band(score, good, warn):
            if score >= good:
                return "Healthy"
            if score >= warn:
                return "Moderate Risk"
            return "Attention"

        margin = float(quote.gross_margin_percent or 0)
        return {
            "overall_health": health.get("score") or float(quote.deal_health_score or 0),
            "health_level": health.get("level"),
            "risk": risk.get("level"),
            "risk_score": risk.get("score") or float(quote.risk_score or 0),
            "margin": "Healthy" if margin >= 18 else ("Attention" if margin >= 12 else "Critical"),
            "discount": "Attention" if (discount.get("blended") or {}).get("has_exceptions") else "Healthy",
            "inventory": "Healthy" if not (fulfillment or {}).get("current", {}).get("backorder_qty") else "Attention",
            "delivery": band(100 - float((fulfillment or {}).get("current", {}).get("delivery_risk") or 0), 75, 50),
            "approval": (
                "Manager Required"
                if approval.get("required")
                else quote.approval_status.value.replace("_", " ").title()
            ),
            "actions": actions,
            "headline": self._headline(quote, risk, health, discount),
        }

    def _headline(self, quote, risk, health, discount) -> str:
        if (discount.get("blended") or {}).get("has_exceptions"):
            return "Discount policy exception is driving risk — Copilot has a safer commercial path."
        if (risk.get("score") or 0) >= 70:
            return "This deal needs governance before it can close."
        if (health.get("score") or 0) >= 75:
            return "Deal is healthy and ready to progress."
        return "A few commercial adjustments will make this deal easier to approve."

    def _discount_impact(self, quote: Quote, product_id: int, new_discount: float) -> dict:
        lines = []
        for ln in quote.lines:
            disc = D(new_discount) if ln.product_id == product_id else D(ln.discount_percent)
            computed = calculate_line(ln.quantity, D(ln.unit_price), D(ln.unit_cost), disc, ln.is_freebie)
            computed["product_id"] = ln.product_id
            lines.append(computed)
        new_tot = calculate_totals(lines, D(quote.shipping_total or 0), D(quote.tax_percent or 18))
        return {
            "current_margin": float(quote.gross_margin_percent or 0),
            "expected_margin": float(new_tot["gross_margin_percent"]),
            "revenue_impact": float(money(new_tot["net_revenue"] - D(quote.subtotal - quote.discount_total))),
            "profit_impact": float(money(new_tot["gross_profit"] - D(quote.gross_profit))),
            "risk_from": float(quote.risk_score or 0),
        }
