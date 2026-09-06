from copy import deepcopy
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.quote import DealSimulation, Quote
from app.models.user import User
from app.services.copilot import DealCopilotService
from app.services.discount import evaluate_line_discount, load_discount_rules
from app.services.fulfillment import WarehouseAllocationService
from app.services.pricing import calculate_line, calculate_totals
from app.services.quote import quote_engine
from app.services.recommendation import RecommendationService
from app.utils.money import D, money


class DealOptimizerService:
    def optimize(self, db: Session, quote: Quote) -> dict:
        intel = quote_engine.recalculate(db, quote)
        fulfillment = WarehouseAllocationService().optimize(db, quote, quote.customer, persist_recommended=True)
        recs = RecommendationService().for_quote(db, quote)
        rules = load_discount_rules(db)

        current = self._snapshot(quote, intel, fulfillment["current"])
        proposed_lines = []
        changes = []
        for ln in quote.lines:
            ev = evaluate_line_discount(rules, quote.customer, ln.product, D(ln.discount_percent))
            new_disc = D(ln.discount_percent)
            if D(ev["exception_percent"]) > 0:
                new_disc = D(ev["allowed_percent"]) + D(4)
                new_disc = min(D(ln.discount_percent), max(D(ev["allowed_percent"]), new_disc))
                changes.append(
                    {
                        "type": "DISCOUNT",
                        "description": f"Reduce {ln.product.name} discount {float(ln.discount_percent):.0f}% → {float(new_disc):.0f}%",
                        "product_id": ln.product_id,
                        "from": float(ln.discount_percent),
                        "to": float(new_disc),
                    }
                )
            computed = calculate_line(ln.quantity, D(ln.unit_price), D(ln.unit_cost), new_disc, ln.is_freebie)
            computed["product_id"] = ln.product_id
            proposed_lines.append(computed)

        added = []
        if recs:
            top = recs[0]
            added.append(top)
            changes.append(
                {
                    "type": "UPSELL",
                    "description": f"Add {top['product_name']} (₹{top['additional_revenue']:,.0f} revenue)",
                    "product_id": top["recommended_product_id"],
                }
            )
            from app.models.catalog import Product
            from app.services.pricing import resolve_unit_cost, resolve_unit_price

            p = db.get(Product, top["recommended_product_id"])
            extra = calculate_line(1, resolve_unit_price(db, p, None, quote.customer, 1), resolve_unit_cost(p, None), D(0))
            extra["product_id"] = p.id
            proposed_lines.append(extra)

        new_ship = D(fulfillment["recommended"]["shipping_cost"])
        if fulfillment["recommended"]["shipments"] != fulfillment["current"]["shipments"]:
            changes.append(
                {
                    "type": "FULFILLMENT",
                    "description": (
                        f"Shipments {fulfillment['current']['shipments']} → {fulfillment['recommended']['shipments']}"
                    ),
                }
            )
        totals = calculate_totals(proposed_lines, new_ship, D(quote.tax_percent or 18))
        optimized = {
            "revenue": float(totals["net_revenue"]),
            "total": float(totals["total"]),
            "margin": float(totals["gross_margin_percent"]),
            "profit": float(totals["gross_profit"]),
            "discount": float(totals["discount_total"]),
            "shipping": float(totals["shipping_total"]),
            "shipments": fulfillment["recommended"]["shipments"],
            "risk": max(float(quote.risk_score) - 20, 15),
        }
        return {
            "current": current,
            "optimized": optimized,
            "changes": changes,
            "savings": {
                "shipping": fulfillment["savings"],
                "discount_given_back": float(money(D(quote.discount_total) - totals["discount_total"])),
            },
            "profit_impact": {
                "amount": float(money(totals["gross_profit"] - D(quote.gross_profit))),
            },
            "risk_change": {
                "from": float(quote.risk_score),
                "to": optimized["risk"],
            },
            "shipment_change": {
                "from": fulfillment["current"]["shipments"],
                "to": fulfillment["recommended"]["shipments"],
            },
            "recommendations": recs[:3],
            "fulfillment": fulfillment,
        }

    def apply(self, db: Session, quote: Quote, user: User, result: dict) -> Quote:
        rules = load_discount_rules(db)
        for ln in quote.lines:
            ev = evaluate_line_discount(rules, quote.customer, ln.product, D(ln.discount_percent))
            if D(ev["exception_percent"]) > 0:
                ln.discount_percent = min(D(ln.discount_percent), D(ev["allowed_percent"]) + D(4))
        recs = result.get("recommendations") or []
        if recs:
            existing = {l.product_id for l in quote.lines}
            pid = recs[0]["recommended_product_id"]
            if pid not in existing:
                quote_engine.add_product(db, quote, user, pid, 1, 0)
        try:
            WarehouseAllocationService().apply_recommended(db, quote)
        except ValueError:
            pass
        quote_engine.recalculate(db, quote)
        from app.models.enums import EventType
        from app.events.bus import event_bus

        event_bus.publish(
            EventType.OPTIMIZATION_APPLIED,
            {"quote_id": quote.id, "actor_id": user.id, "description": "Optimized deal applied"},
            db,
        )
        db.flush()
        return quote

    def _snapshot(self, quote: Quote, intel: dict, fulfillment: dict) -> dict:
        return {
            "revenue": float(quote.subtotal - quote.discount_total),
            "total": float(quote.total),
            "margin": float(quote.gross_margin_percent),
            "profit": float(quote.gross_profit),
            "discount": float(quote.discount_total),
            "shipping": float(quote.shipping_total),
            "shipments": fulfillment.get("shipments") if fulfillment else quote.shipment_count,
            "risk": float(quote.risk_score),
            "health": float(quote.deal_health_score),
        }


class SimulationService:
    def run(self, db: Session, quote: Quote, user: User, scenario: dict) -> dict:
        intel = quote_engine.recalculate(db, quote)
        current = {
            "revenue": float(quote.subtotal - quote.discount_total),
            "margin": float(quote.gross_margin_percent),
            "risk": float(quote.risk_score),
            "profit": float(quote.gross_profit),
            "total": float(quote.total),
            "shipments": quote.shipment_count,
        }
        line_overrides = {int(k): v for k, v in (scenario.get("line_discounts") or {}).items()}
        qty_overrides = {int(k): v for k, v in (scenario.get("line_quantities") or {}).items()}
        add_products = list(scenario.get("add_product_ids") or [])
        proposed = []
        from app.models.catalog import Product
        from app.services.pricing import resolve_unit_cost, resolve_unit_price

        for ln in quote.lines:
            disc = D(line_overrides.get(ln.id, ln.discount_percent))
            qty = int(qty_overrides.get(ln.id, ln.quantity))
            computed = calculate_line(qty, D(ln.unit_price), D(ln.unit_cost), disc, ln.is_freebie)
            computed["product_id"] = ln.product_id
            proposed.append(computed)
        for pid in add_products:
            p = db.get(Product, int(pid))
            if not p:
                continue
            extra = calculate_line(1, resolve_unit_price(db, p, None, quote.customer, 1), resolve_unit_cost(p, None), D(0))
            extra["product_id"] = p.id
            proposed.append(extra)
        shipping = D(quote.shipping_total or 0)
        if scenario.get("consolidate_warehouse"):
            shipping = money(shipping * D("0.65"))
        totals = calculate_totals(proposed, shipping, D(quote.tax_percent or 18))
        # Approximate risk: lower if discounts drop
        risk = float(quote.risk_score)
        for ln in quote.lines:
            if ln.id in line_overrides and D(line_overrides[ln.id]) < D(ln.discount_percent):
                risk -= float(D(ln.discount_percent) - D(line_overrides[ln.id])) * 2.2
        if add_products:
            risk -= 6
        if scenario.get("consolidate_warehouse"):
            risk -= 8
        risk = max(8, min(100, risk))
        projected = {
            "revenue": float(totals["net_revenue"]),
            "margin": float(totals["gross_margin_percent"]),
            "risk": round(risk, 1),
            "profit": float(totals["gross_profit"]),
            "total": float(totals["total"]),
            "shipments": 2 if scenario.get("consolidate_warehouse") else quote.shipment_count,
        }
        result = {
            "current": current,
            "projected": projected,
            "deltas": {
                "revenue": projected["revenue"] - current["revenue"],
                "margin": projected["margin"] - current["margin"],
                "risk": projected["risk"] - current["risk"],
                "profit": projected["profit"] - current["profit"],
            },
            "scenario": scenario,
        }
        sim = DealSimulation(
            quote_id=quote.id,
            created_by=user.id,
            name=scenario.get("name") or "Scenario",
            input_snapshot_json=scenario,
            result_snapshot_json=result,
            revenue_delta=D(result["deltas"]["revenue"]),
            margin_delta=D(result["deltas"]["margin"]),
            risk_delta=D(result["deltas"]["risk"]),
        )
        db.add(sim)
        db.flush()
        result["simulation_id"] = sim.id
        return result

    def apply(self, db: Session, quote: Quote, user: User, simulation_id: int) -> Quote:
        sim = db.get(DealSimulation, simulation_id)
        if not sim or sim.quote_id != quote.id:
            from app.core.exceptions import AppError

            raise AppError("NOT_FOUND", "Simulation not found.", 404)
        scenario = sim.input_snapshot_json or {}
        line_overrides = {int(k): v for k, v in (scenario.get("line_discounts") or {}).items()}
        qty_overrides = {int(k): v for k, v in (scenario.get("line_quantities") or {}).items()}
        for ln in quote.lines:
            if ln.id in line_overrides:
                ln.discount_percent = D(line_overrides[ln.id])
            if ln.id in qty_overrides:
                ln.quantity = int(qty_overrides[ln.id])
        for pid in scenario.get("add_product_ids") or []:
            if not any(l.product_id == int(pid) for l in quote.lines):
                quote_engine.add_product(db, quote, user, int(pid), 1, 0)
        if scenario.get("payment_terms"):
            quote.payment_terms = int(scenario["payment_terms"])
        if scenario.get("consolidate_warehouse"):
            try:
                WarehouseAllocationService().optimize(db, quote, quote.customer, persist_recommended=True)
                WarehouseAllocationService().apply_recommended(db, quote)
            except Exception:
                pass
        quote_engine.recalculate(db, quote)
        from app.events.bus import event_bus
        from app.models.enums import EventType

        event_bus.publish(
            EventType.SIMULATION_APPLIED,
            {"quote_id": quote.id, "actor_id": user.id, "description": "What-if scenario applied to quote"},
            db,
        )
        db.flush()
        return quote
