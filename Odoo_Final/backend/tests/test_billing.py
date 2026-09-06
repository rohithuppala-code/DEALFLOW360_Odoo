from app.models.enums import BillingInterval
from app.services.billing import BillingService, to_mrr
from app.utils.money import D


def test_proration_upgrade():
    svc = BillingService()
    result = svc.prorate(D(20000), D(35000), 12, 30)
    # unused old = 20000*12/30 = 8000; new partial = 35000*12/30 = 14000; adj = 6000
    assert result["credit"] == 8000.0
    assert result["new_charge"] == 14000.0
    assert result["prorated_adjustment"] == 6000.0


def test_mrr_quarterly():
    mrr = to_mrr(D(90000), BillingInterval.QUARTERLY, 1, D(0))
    assert float(mrr) == 30000.0


def test_cancellation_credit_uses_remaining_days():
    svc = BillingService()
    # monthly 30k, 10 days left → 10000 unused
    pr = svc.prorate(D(30000), D(0), 10, 30)
    assert pr["credit"] == 10000.0
    assert pr["prorated_adjustment"] == -10000.0
