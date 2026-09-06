from decimal import Decimal

from app.services.pricing import calculate_line, calculate_totals
from app.utils.money import D


def test_line_margin_and_profit():
    result = calculate_line(10, D(72000), D(52000), D(12))
    assert result["gross"] == D("720000.00")
    assert result["discount_amount"] == D("86400.00")
    assert result["net_amount"] == D("633600.00")
    assert result["total_cost"] == D("520000.00")
    assert result["gross_profit"] == D("113600.00")
    assert float(result["margin_percent"]) == 17.9293  # 113600/633600*100


def test_zero_net_does_not_divide():
    result = calculate_line(1, D(100), D(40), D(100))
    assert result["net_amount"] == D("0.00")
    assert result["margin_percent"] == D("0.0000")


def test_totals_tax():
    lines = [calculate_line(1, D(1000), D(400), D(10))]
    tot = calculate_totals(lines, D(100), D(18))
    # net 900 + ship 100 = 1000 taxable, tax 180, total 1180
    assert tot["net_revenue"] == D("900.00")
    assert tot["tax_total"] == D("180.00")
    assert tot["total"] == D("1180.00")
