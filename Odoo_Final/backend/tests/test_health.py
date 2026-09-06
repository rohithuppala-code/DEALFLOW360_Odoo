from app.models.enums import ApprovalStatus
from app.services.health import compute_health, health_level
from app.utils.money import D


def test_healthy_deal():
    h = compute_health(
        margin_percent=D(24),
        risk_score=D(20),
        quote_age_days=2,
        approval_status=ApprovalStatus.APPROVED,
        approval_pending_days=0,
        inventory_ok=True,
        backorder_qty=0,
        negotiation_open=False,
        customer_engaged=True,
        payment_terms=30,
    )
    assert h["score"] >= 75
    assert health_level(D(h["score"])) == "HEALTHY"
    assert "Margin" in h["strengths"]


def test_risky_deal_composition():
    h = compute_health(
        margin_percent=D(11),
        risk_score=D(78),
        quote_age_days=14,
        approval_status=ApprovalStatus.PENDING,
        approval_pending_days=3,
        inventory_ok=False,
        backorder_qty=4,
        negotiation_open=True,
        customer_engaged=True,
        payment_terms=60,
    )
    assert h["score"] < 55
    assert any("Approval delayed" in r for r in h["risks"])
