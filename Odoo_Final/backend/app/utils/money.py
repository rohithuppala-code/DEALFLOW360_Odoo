from decimal import ROUND_HALF_UP, Decimal

TWOPLACES = Decimal("0.01")
FOURPLACES = Decimal("0.0001")
ZERO = Decimal("0.00")


def D(value) -> Decimal:
    if value is None:
        return ZERO
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def money(value) -> Decimal:
    return D(value).quantize(TWOPLACES, rounding=ROUND_HALF_UP)


def pct(value) -> Decimal:
    return D(value).quantize(FOURPLACES, rounding=ROUND_HALF_UP)


def safe_div(num, den) -> Decimal:
    n, d = D(num), D(den)
    if d == 0:
        return ZERO
    return n / d


def clamp(value, lo=0, hi=100) -> Decimal:
    v = D(value)
    return max(D(lo), min(D(hi), v))


def inr_compact(value) -> str:
    amount = D(value)
    abs_amount = abs(amount)
    sign = "-" if amount < 0 else ""
    if abs_amount >= Decimal("10000000"):
        return f"{sign}₹{(abs_amount / Decimal('10000000')):.2f} Cr"
    if abs_amount >= Decimal("100000"):
        return f"{sign}₹{(abs_amount / Decimal('100000')):.2f}L"
    return f"{sign}₹{abs_amount:,.0f}"
