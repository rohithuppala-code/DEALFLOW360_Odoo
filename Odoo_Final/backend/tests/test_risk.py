from app.services.risk import risk_level, score_deal
from app.utils.money import D


def test_risk_bands():
    assert risk_level(D(10)) == "LOW"
    assert risk_level(D(45)) == "MEDIUM"
    assert risk_level(D(70)) == "HIGH"
    assert risk_level(D(90)) == "CRITICAL"


def test_blended_service_exception_raises_risk():
    evaluations = [
        {
            "product_name": "Laptop Pro",
            "requested_percent": 12,
            "allowed_percent": 15,
            "exception_percent": 0,
            "rule_name": "Gold Hardware",
            "product_id": 1,
        },
        {
            "product_name": "Implementation Service",
            "requested_percent": 18,
            "allowed_percent": 10,
            "exception_percent": 8,
            "rule_name": "Gold Services",
            "product_id": 2,
        },
    ]
    blended = {
        "has_exceptions": True,
        "exception_count": 1,
        "total_exception_points": 8,
        "max_exception_points": 8,
        "evaluations": evaluations,
    }
    result = score_deal(
        discount_evaluations=evaluations,
        blended=blended,
        margin_percent=D("16.5"),
        customer_tier="Gold",
        customer_risk_multiplier=D(1),
        payment_terms=30,
        shipment_count=3,
        backorder_qty=0,
        requested_qty=12,
        negotiation_count=0,
        rep_avg_discount=D("8.5"),
        deal_discount_percent=D("14"),
        deal_value=D("800000"),
        historical_avg_deal=D("300000"),
    )
    assert result["score"] >= 30
    types = {f["type"] for f in result["factors"]}
    assert "CATEGORY_DISCOUNT_EXCEPTION" in types
    assert "LOW_MARGIN" in types
    assert any("exceeds" in f["message"].lower() for f in result["factors"])


def test_low_risk_clean_deal():
    result = score_deal(
        discount_evaluations=[
            {
                "product_name": "Laptop",
                "requested_percent": 5,
                "allowed_percent": 15,
                "exception_percent": 0,
                "rule_name": "Gold Hardware",
                "product_id": 1,
            }
        ],
        blended={"has_exceptions": False, "exception_count": 0, "total_exception_points": 0, "max_exception_points": 0, "evaluations": []},
        margin_percent=D("28"),
        customer_tier="Platinum",
        customer_risk_multiplier=D("0.7"),
        payment_terms=15,
        shipment_count=1,
        backorder_qty=0,
        requested_qty=4,
        negotiation_count=0,
        rep_avg_discount=D("8"),
        deal_discount_percent=D("5"),
        deal_value=D("200000"),
        historical_avg_deal=D("250000"),
    )
    assert result["level"] in ("LOW", "MEDIUM")
    assert result["score"] < 40
