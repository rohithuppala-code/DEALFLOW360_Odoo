from decimal import Decimal

from app.models.catalog import Product
from app.utils.money import D, ZERO, money, pct, safe_div


class MarginGuardianService:
    """Explains how discounts trade customer savings for seller profit."""

    def analyze(self, lines: list[dict], products: dict[int, Product], target_margin: Decimal = D(18)) -> dict:
        warnings: list[dict] = []
        total_customer_saving = ZERO
        total_profit_lost = ZERO

        for ln in lines:
            product = products.get(ln["product_id"])
            if not product:
                continue
            qty = D(ln["quantity"])
            list_rev = money(D(ln["unit_price"]) * qty)
            net = D(ln["net_amount"])
            cost = D(ln["total_cost"])
            saving = money(list_rev - net)
            full_profit = money(list_rev - cost)
            actual_profit = D(ln["gross_profit"])
            lost = money(full_profit - actual_profit)
            total_customer_saving += saving
            total_profit_lost += lost

            if D(ln["margin_percent"]) < target_margin and saving > 0:
                suggested_disc = self._suggested_discount(D(ln["unit_price"]), D(ln["unit_cost"]), target_margin)
                warnings.append(
                    {
                        "product": product.name,
                        "line_id": ln.get("id"),
                        "customer_saving": float(saving),
                        "profit_lost": float(lost),
                        "current_discount": float(ln["discount_percent"]),
                        "current_margin": float(ln["margin_percent"]),
                        "suggested_discount": float(suggested_disc),
                        "message": (
                            f"This discount saves the customer ₹{saving:,.0f} "
                            f"but reduces deal profit by ₹{lost:,.0f}."
                        ),
                    }
                )

        recommendation = None
        if warnings:
            worst = max(warnings, key=lambda w: w["profit_lost"])
            # alternative: slightly lower discount + free installation perceived value
            recommendation = {
                "title": "Protect margin without shrinking customer value",
                "recommended": f"Offer {worst['suggested_discount']:.0f}% discount + a high-perceived-value add-on instead of {worst['current_discount']:.0f}%.",
                "customer_value": float(total_customer_saving),
                "profit_preserved": float(max(ZERO, total_profit_lost * D("0.55"))),
            }

        return {
            "customer_saving": float(money(total_customer_saving)),
            "profit_lost": float(money(total_profit_lost)),
            "warnings": warnings,
            "recommendation": recommendation,
            "healthy": len(warnings) == 0,
        }

    def _suggested_discount(self, unit_price: Decimal, unit_cost: Decimal, target_margin: Decimal) -> Decimal:
        if unit_price <= 0:
            return ZERO
        # net = cost / (1 - target/100)
        target_net = unit_cost / (D(1) - target_margin / D(100)) if target_margin < 100 else unit_cost
        disc = (D(1) - safe_div(target_net, unit_price)) * D(100)
        disc = max(ZERO, min(D(40), disc))
        return pct(disc)
