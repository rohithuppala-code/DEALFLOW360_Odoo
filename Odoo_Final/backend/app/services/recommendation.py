from sqlalchemy.orm import Session, joinedload

from app.models.catalog import Product
from app.models.intelligence import RecommendationRule
from app.models.quote import Quote
from app.services.pricing import calculate_line, calculate_totals, resolve_unit_cost, resolve_unit_price
from app.utils.money import D, money


class RecommendationService:
    def for_quote(self, db: Session, quote: Quote) -> list[dict]:
        existing = {ln.product_id for ln in quote.lines}
        return self._from_rules(db, existing, customer=quote.customer, quote=quote)

    def for_product_ids(self, db: Session, product_ids: list[int], customer=None) -> list[dict]:
        return self._from_rules(db, set(product_ids or []), customer=customer, quote=None)

    def _from_rules(self, db: Session, existing: set[int], customer=None, quote: Quote | None = None) -> list[dict]:
        if not existing:
            return []
        rules = (
            db.query(RecommendationRule)
            .options(joinedload(RecommendationRule.recommended_product))
            .filter(RecommendationRule.is_active.is_(True), RecommendationRule.product_id.in_(existing))
            .order_by(RecommendationRule.priority.desc())
            .all()
        )
        out = []
        seen: set[int] = set()
        for rule in rules:
            if rule.recommended_product_id in existing or rule.recommended_product_id in seen:
                continue
            product = rule.recommended_product or db.get(Product, rule.recommended_product_id)
            if not product or not product.is_active:
                continue
            seen.add(product.id)
            if quote is not None:
                impact = self.margin_impact(db, quote, product, 1)
            else:
                impact = self.product_impact(db, product, customer, 1)
            from app.services.settings import get_setting

            min_margin = float(get_setting(db, "recommendations.min_margin_percent", 0) or 0)
            if min_margin and float(impact["after"]["margin"]) < min_margin:
                continue
            priority_label = "HIGH" if rule.priority >= 80 else ("MEDIUM" if rule.priority >= 50 else "LOW")
            out.append(
                {
                    "id": rule.id,
                    "recommendation_type": rule.recommendation_type.value,
                    "priority": rule.priority,
                    "priority_label": priority_label,
                    "reason": rule.reason,
                    "confidence": rule.confidence,
                    "product_id": rule.product_id,
                    "recommended_product_id": product.id,
                    "product_name": product.name,
                    "sku": product.sku,
                    "unit_price": float(product.base_price),
                    "product_type": product.product_type.value,
                    "category": product.category.name if getattr(product, "category", None) else None,
                    "additional_revenue": impact["delta"]["revenue"],
                    "additional_profit": impact["delta"]["profit"],
                    "projected": impact["after"],
                    "before": impact["before"],
                }
            )
        return out

    def product_impact(self, db: Session, product: Product, customer, quantity: int = 1) -> dict:
        unit_price = resolve_unit_price(db, product, None, customer, quantity)
        unit_cost = resolve_unit_cost(product, None)
        extra = calculate_line(quantity, unit_price, unit_cost, D(0))
        after = {
            "revenue": float(extra["net_amount"]),
            "cost": float(extra["total_cost"]),
            "profit": float(extra["gross_profit"]),
            "margin": float(extra["margin_percent"]),
        }
        return {
            "before": {"revenue": 0, "cost": 0, "profit": 0, "margin": 0},
            "after": after,
            "delta": {
                "revenue": float(extra["net_amount"]),
                "cost": float(extra["total_cost"]),
                "profit": float(extra["gross_profit"]),
                "margin": float(extra["margin_percent"]),
            },
        }

    def margin_impact(self, db: Session, quote: Quote, product: Product, quantity: int = 1) -> dict:
        before = {
            "revenue": float(quote.subtotal - quote.discount_total),
            "cost": float(quote.cost_total),
            "profit": float(quote.gross_profit),
            "margin": float(quote.gross_margin_percent),
        }
        unit_price = resolve_unit_price(db, product, None, quote.customer, quantity)
        unit_cost = resolve_unit_cost(product, None)
        extra = calculate_line(quantity, unit_price, unit_cost, D(0))
        after_rev = money(D(before["revenue"]) + extra["net_amount"])
        after_cost = money(D(before["cost"]) + extra["total_cost"])
        after_profit = money(after_rev - after_cost)
        after_margin = float((after_profit / after_rev * 100) if after_rev else 0)
        after = {
            "revenue": float(after_rev),
            "cost": float(after_cost),
            "profit": float(after_profit),
            "margin": round(after_margin, 2),
        }
        return {
            "before": before,
            "after": after,
            "delta": {
                "revenue": float(extra["net_amount"]),
                "cost": float(extra["total_cost"]),
                "profit": float(extra["gross_profit"]),
                "margin": round(after_margin - before["margin"], 2),
            },
        }
