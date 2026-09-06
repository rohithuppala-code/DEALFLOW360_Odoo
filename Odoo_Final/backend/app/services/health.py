from datetime import datetime
from decimal import Decimal

from app.models.enums import ApprovalStatus, HealthLevel, QuoteStatus
from app.utils.money import D, clamp


def health_level(score: Decimal) -> str:
    s = float(score)
    if s >= 75:
        return HealthLevel.HEALTHY
    if s >= 55:
        return HealthLevel.WATCH
    if s >= 35:
        return HealthLevel.AT_RISK
    return HealthLevel.CRITICAL


def compute_health(
    *,
    margin_percent: Decimal,
    risk_score: Decimal,
    quote_age_days: int,
    approval_status: ApprovalStatus,
    approval_pending_days: int,
    inventory_ok: bool,
    backorder_qty: int,
    negotiation_open: bool,
    customer_engaged: bool,
    payment_terms: int,
    followups: int = 0,
) -> dict:
    components = []
    score = D(50)

    # Margin +18 max
    if margin_percent >= 22:
        m = D(18)
    elif margin_percent >= 18:
        m = D(14)
    elif margin_percent >= 12:
        m = D(6)
    else:
        m = D(-8)
    score += m
    components.append({"key": "margin", "label": "Margin", "points": float(m), "ok": m > 0})

    # Inventory +12
    inv = D(12) if inventory_ok and backorder_qty == 0 else (D(4) if backorder_qty > 0 else D(-6))
    score += inv
    components.append({"key": "inventory", "label": "Inventory", "points": float(inv), "ok": inv > 0})

    # Customer +16
    cust = D(16) if customer_engaged else D(6)
    if negotiation_open:
        cust -= D(4)
    score += cust
    components.append({"key": "customer", "label": "Customer", "points": float(cust), "ok": cust > 8})

    # Approval +14
    if approval_status in (ApprovalStatus.APPROVED, ApprovalStatus.NOT_REQUIRED):
        appr = D(14)
    elif approval_status == ApprovalStatus.PENDING:
        appr = D(4) - D(min(approval_pending_days, 5) * 2)
    elif approval_status == ApprovalStatus.REJECTED:
        appr = D(-10)
    else:
        appr = D(6)
    score += appr
    components.append({"key": "approval", "label": "Approval", "points": float(appr), "ok": appr > 0})

    # Delivery +10
    deliv = D(10) if backorder_qty == 0 else D(-4)
    score += deliv
    components.append({"key": "delivery", "label": "Delivery", "points": float(deliv), "ok": deliv > 0})

    # Negotiation +8
    nego = D(8) if not negotiation_open else D(2)
    score += nego
    components.append({"key": "negotiation", "label": "Negotiation", "points": float(nego), "ok": not negotiation_open})

    # Age / risk penalties
    age_pen = D(min(quote_age_days, 21)) * D("0.6")
    score -= age_pen
    risk_pen = D(risk_score) * D("0.18")
    score -= risk_pen
    if payment_terms > 45:
        score -= D(4)

    score = clamp(score, 0, 100)
    strengths = [c["label"] for c in components if c["ok"] and c["points"] >= 8]
    risks = []
    if float(risk_score) >= 60:
        risks.append("Elevated commercial risk")
    if approval_status == ApprovalStatus.PENDING and approval_pending_days >= 2:
        risks.append(f"Approval delayed {approval_pending_days} days")
    if negotiation_open:
        risks.append("Customer requested additional commercial changes")
    if backorder_qty > 0:
        risks.append("Inventory backorder on this deal")
    if quote_age_days > 10:
        risks.append(f"Quote aging {quote_age_days} days")

    return {
        "score": float(score),
        "level": health_level(score),
        "components": components,
        "strengths": strengths or ["Deal is progressing"],
        "risks": risks,
    }
