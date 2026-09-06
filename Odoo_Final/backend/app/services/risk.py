from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.intelligence import SystemSetting
from app.models.quote import Quote
from app.utils.money import D, ZERO, clamp, money, pct

DEFAULT_WEIGHTS = {
    "discount_exception": 3.0,
    "discount_exception_cap": 40,
    "low_margin": 2.0,
    "low_margin_cap": 25,
    "target_margin": 18.0,
    "delivery": 1.0,
    "delivery_cap": 15,
    "inventory": 1.0,
    "inventory_cap": 15,
    "negotiation": 5.0,
    "negotiation_cap": 15,
    "customer_bronze": 8,
    "customer_silver": 5,
    "customer_gold": 2,
    "customer_platinum": 0,
    "anomaly_cap": 12,
    "deal_size_cap": 8,
    "payment_terms_cap": 10,
}


def risk_level(score: Decimal) -> str:
    s = float(score)
    if s <= 29:
        return "LOW"
    if s <= 59:
        return "MEDIUM"
    if s <= 79:
        return "HIGH"
    return "CRITICAL"


def load_weights(db: Session | None) -> dict:
    if db is None:
        return dict(DEFAULT_WEIGHTS)
    row = db.query(SystemSetting).filter(SystemSetting.key == "risk_weights").first()
    if not row:
        return dict(DEFAULT_WEIGHTS)
    merged = dict(DEFAULT_WEIGHTS)
    merged.update(row.value_json or {})
    return merged


def score_deal(
    *,
    discount_evaluations: list[dict],
    blended: dict,
    margin_percent: Decimal,
    customer_tier: str,
    customer_risk_multiplier: Decimal,
    payment_terms: int,
    shipment_count: int,
    backorder_qty: int,
    requested_qty: int,
    negotiation_count: int,
    rep_avg_discount: Decimal | None,
    deal_discount_percent: Decimal,
    deal_value: Decimal,
    historical_avg_deal: Decimal | None,
    weights: dict | None = None,
) -> dict:
    w = weights or DEFAULT_WEIGHTS
    factors: list[dict] = []

    # Discount exceptions
    if blended.get("has_exceptions"):
        pts = min(
            D(20) + D(w["discount_exception"]) * D(blended["total_exception_points"]),
            D(w["discount_exception_cap"]),
        )
        # extra for multiple exceptions
        if blended["exception_count"] > 1:
            pts += D(4)
        pts = min(pts, D(w["discount_exception_cap"]))
        for ev in discount_evaluations:
            if D(ev["exception_percent"]) > 0:
                factors.append(
                    {
                        "type": "CATEGORY_DISCOUNT_EXCEPTION",
                        "severity": float(money(pts if len([e for e in discount_evaluations if D(e['exception_percent']) > 0]) == 1 else D(ev["exception_percent"]) * D(w["discount_exception"]))),
                        "weight": w["discount_exception"],
                        "message": (
                            f"{ev['product_name']} discount {float(ev['requested_percent']):.0f}% exceeds "
                            f"{ev.get('rule_name') or customer_tier} limit of {float(ev['allowed_percent']):.0f}% "
                            f"by {float(ev['exception_percent']):.0f}%"
                        ),
                        "metadata": ev,
                    }
                )
        # replace per-line severities so they sum to pts
        if factors:
            per = float(money(pts / D(len([f for f in factors if f['type'] == 'CATEGORY_DISCOUNT_EXCEPTION']))))
            for f in factors:
                if f["type"] == "CATEGORY_DISCOUNT_EXCEPTION":
                    f["severity"] = per

    # Margin
    target = D(w["target_margin"])
    if margin_percent < target:
        gap = target - D(margin_percent)
        pts = min(gap * D(w["low_margin"]), D(w["low_margin_cap"]))
        factors.append(
            {
                "type": "LOW_MARGIN",
                "severity": float(money(pts)),
                "weight": w["low_margin"],
                "message": f"Blended margin {float(margin_percent):.1f}% is below the {float(target):.0f}% target by {float(gap):.1f} points",
                "metadata": {"margin": float(margin_percent), "target": float(target)},
            }
        )

    # Delivery / shipments
    delivery_pts = ZERO
    if shipment_count > 2:
        delivery_pts += D(6) * D(shipment_count - 2)
    if backorder_qty > 0:
        delivery_pts += D(8)
    delivery_pts = min(delivery_pts * D(w["delivery"]), D(w["delivery_cap"]))
    if delivery_pts > 0:
        msg = []
        if shipment_count > 2:
            msg.append(f"{shipment_count} shipments increase delivery complexity")
        if backorder_qty > 0:
            msg.append(f"{backorder_qty} units backordered")
        factors.append(
            {
                "type": "DELIVERY_RISK",
                "severity": float(money(delivery_pts)),
                "weight": w["delivery"],
                "message": "; ".join(msg) or "Delivery risk detected",
                "metadata": {"shipments": shipment_count, "backorder_qty": backorder_qty},
            }
        )

    # Inventory
    if requested_qty > 0 and backorder_qty > 0:
        shortfall = D(backorder_qty) / D(requested_qty) * D(100)
        inv_pts = min(shortfall * D("0.4") * D(w["inventory"]), D(w["inventory_cap"]))
        if inv_pts > 0:
            factors.append(
                {
                    "type": "INVENTORY_RISK",
                    "severity": float(money(inv_pts)),
                    "weight": w["inventory"],
                    "message": f"Inventory shortfall of {float(shortfall):.0f}% across requested hardware",
                    "metadata": {"backorder_qty": backorder_qty, "requested_qty": requested_qty},
                }
            )

    # Negotiation
    if negotiation_count > 0:
        npts = min(D(negotiation_count) * D(w["negotiation"]), D(w["negotiation_cap"]))
        factors.append(
            {
                "type": "NEGOTIATION_FREQUENCY",
                "severity": float(money(npts)),
                "weight": w["negotiation"],
                "message": f"{negotiation_count} open/recent negotiation request(s) on this deal",
                "metadata": {"count": negotiation_count},
            }
        )

    # Customer tier
    tier_key = f"customer_{customer_tier.lower()}"
    cust_pts = D(w.get(tier_key, 3)) * D(customer_risk_multiplier)
    if cust_pts > 0:
        factors.append(
            {
                "type": "CUSTOMER_RISK",
                "severity": float(money(cust_pts)),
                "weight": 1,
                "message": f"{customer_tier} tier customer risk multiplier {float(customer_risk_multiplier):.2f}",
                "metadata": {"tier": customer_tier},
            }
        )

    # Rep anomaly
    if rep_avg_discount is not None and D(rep_avg_discount) > 0:
        delta = D(deal_discount_percent) - D(rep_avg_discount)
        if delta > D(4):
            apts = min(delta * D("1.2"), D(w["anomaly_cap"]))
            factors.append(
                {
                    "type": "REP_ANOMALY",
                    "severity": float(money(apts)),
                    "weight": 1,
                    "message": (
                        f"Deal discount {float(deal_discount_percent):.1f}% is "
                        f"+{float(delta):.1f} points above this rep's historical average of {float(rep_avg_discount):.1f}%"
                    ),
                    "metadata": {"rep_avg": float(rep_avg_discount), "deal": float(deal_discount_percent)},
                }
            )

    # Deal size
    if historical_avg_deal and historical_avg_deal > 0 and deal_value > historical_avg_deal * D(3):
        ratio = deal_value / historical_avg_deal
        spts = min(D(ratio) * D(2), D(w["deal_size_cap"]))
        factors.append(
            {
                "type": "DEAL_SIZE",
                "severity": float(money(spts)),
                "weight": 1,
                "message": f"Deal value is {float(ratio):.1f}× this customer's historical average",
                "metadata": {"ratio": float(ratio)},
            }
        )

    # Payment terms
    if payment_terms > 45:
        ppts = D(5) if payment_terms <= 60 else D(w["payment_terms_cap"])
        factors.append(
            {
                "type": "PAYMENT_TERMS",
                "severity": float(money(ppts)),
                "weight": 1,
                "message": f"Payment terms of {payment_terms} days exceed the 45-day standard",
                "metadata": {"days": payment_terms},
            }
        )

    raw = sum((D(f["severity"]) for f in factors), ZERO)
    score = clamp(raw, 0, 100)
    return {
        "score": float(score),
        "level": risk_level(score),
        "factors": factors,
    }


def persist_factors(db: Session, quote: Quote, result: dict) -> None:
    from app.models.quote import RiskFactor

    db.query(RiskFactor).filter(RiskFactor.quote_id == quote.id).delete()
    for f in result["factors"]:
        db.add(
            RiskFactor(
                quote_id=quote.id,
                factor_type=f["type"],
                severity=D(f["severity"]),
                weight=D(f.get("weight") or 1),
                message=f["message"],
                metadata_json=f.get("metadata"),
            )
        )
    quote.risk_score = D(result["score"])
