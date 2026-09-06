from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.catalog import Product
from app.models.customer import Customer
from app.models.governance import DiscountRule
from app.utils.money import D, ZERO, money, pct


def load_discount_rules(db: Session) -> list[DiscountRule]:
    return db.query(DiscountRule).filter(DiscountRule.is_active.is_(True)).all()


def matching_rule(rules: list[DiscountRule], customer: Customer, product: Product) -> DiscountRule | None:
    """Most specific matching rule: product > category+tier > category > tier > global."""
    scored: list[tuple[int, DiscountRule]] = []
    for rule in rules:
        if rule.customer_tier_id and rule.customer_tier_id != customer.customer_tier_id:
            continue
        if rule.product_id and rule.product_id != product.id:
            continue
        if rule.category_id and rule.category_id != product.category_id:
            continue
        score = 0
        if rule.product_id:
            score += 8
        if rule.category_id:
            score += 4
        if rule.customer_tier_id:
            score += 2
        scored.append((score, rule))
    if not scored:
        return None
    scored.sort(key=lambda x: (-x[0], x[1].max_discount_percent))
    return scored[0][1]


def evaluate_line_discount(
    rules: list[DiscountRule],
    customer: Customer,
    product: Product,
    discount_percent: Decimal,
) -> dict:
    rule = matching_rule(rules, customer, product)
    allowed = D(rule.max_discount_percent) if rule else D(customer.tier.default_discount_limit)
    requested = D(discount_percent)
    exception = money(max(ZERO, requested - allowed))
    return {
        "rule_id": rule.id if rule else None,
        "rule_name": rule.name if rule else f"{customer.tier.name} default",
        "allowed_percent": pct(allowed),
        "requested_percent": pct(requested),
        "exception_percent": pct(exception),
        "requires_approval": bool(rule.requires_approval) if rule and exception > 0 else exception > 0,
        "category_id": product.category_id,
        "category_name": product.category.name if product.category else None,
        "product_id": product.id,
        "product_name": product.name,
        "severity": rule.severity if rule else "MEDIUM",
    }


def line_policy_snapshot(db: Session, quote, pending_requests: list | None = None) -> list[dict]:
    """Allowed vs requested vs excess discount for every quote line."""
    rules = load_discount_rules(db)
    overlay: dict[int, Decimal] = {}
    overlay_name: dict[str, Decimal] = {}
    for req in pending_requests or []:
        status = req.status.value if hasattr(req.status, "value") else str(req.status)
        rtype = req.request_type.value if hasattr(req.request_type, "value") else str(req.request_type)
        if status != "PENDING" or rtype != "DISCOUNT":
            continue
        try:
            requested = D(str(req.requested_value or "").replace("%", ""))
        except Exception:
            continue
        if req.category_id:
            overlay[int(req.category_id)] = requested
        name = None
        if req.old_value and "|" in req.old_value:
            name = req.old_value.split("|", 1)[0]
        elif getattr(req, "category", None):
            name = req.category.name
        if name:
            overlay_name[name.lower()] = requested
    rows = []
    for ln in quote.lines:
        product = ln.product
        if not product:
            continue
        requested = D(ln.discount_percent)
        if product.category_id and int(product.category_id) in overlay:
            requested = overlay[int(product.category_id)]
        elif product.category and product.category.name.lower() in overlay_name:
            requested = overlay_name[product.category.name.lower()]
        ev = evaluate_line_discount(rules, quote.customer, product, requested)
        rows.append(
            {
                "line_id": ln.id,
                "product": product.name,
                "sku": product.sku,
                "category": product.category.name if product.category else None,
                "category_id": product.category_id,
                "quantity": ln.quantity,
                "unit_price": float(ln.unit_price),
                "gross_amount": float(D(ln.quantity) * D(ln.unit_price)),
                "net_amount": float(ln.net_amount),
                "margin_percent": float(ln.margin_percent or 0),
                "current_discount": float(ln.discount_percent),
                "requested_discount": float(ev["requested_percent"]),
                "allowed_discount": float(ev["allowed_percent"]),
                "excess_discount": float(ev["exception_percent"]),
                "rule_name": ev["rule_name"],
            }
        )
    return rows


def blended_exceptions(evaluations: list[dict], order_value: Decimal) -> dict:
    exceptions = [e for e in evaluations if D(e["exception_percent"]) > 0]
    count = len(exceptions)
    total_exception = sum((D(e["exception_percent"]) for e in exceptions), ZERO)
    max_exception = max((D(e["exception_percent"]) for e in exceptions), default=ZERO)
    return {
        "exception_count": count,
        "total_exception_points": pct(total_exception),
        "max_exception_points": pct(max_exception),
        "order_value": money(order_value),
        "has_exceptions": count > 0,
        "evaluations": evaluations,
    }
