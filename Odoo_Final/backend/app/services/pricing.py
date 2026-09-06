from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.catalog import PriceList, PriceListItem, Product, ProductVariant
from app.models.customer import Customer
from app.utils.money import D, money, pct, safe_div, ZERO


def resolve_unit_price(
    db: Session,
    product: Product,
    variant: ProductVariant | None,
    customer: Customer | None,
    quantity: int,
) -> Decimal:
    price = D(product.base_price)
    if variant:
        price += D(variant.price_adjustment)
    if customer:
        plist = (
            db.query(PriceList)
            .filter(PriceList.customer_tier_id == customer.customer_tier_id, PriceList.is_active.is_(True))
            .first()
        )
        if plist:
            q = db.query(PriceListItem).filter(
                PriceListItem.price_list_id == plist.id,
                PriceListItem.product_id == product.id,
            )
            if variant:
                item = q.filter(PriceListItem.variant_id == variant.id).first() or q.filter(
                    PriceListItem.variant_id.is_(None)
                ).first()
            else:
                item = q.filter(PriceListItem.variant_id.is_(None)).first() or q.first()
            if item and quantity >= (item.min_quantity or 1):
                if item.max_quantity is None or quantity <= item.max_quantity:
                    price = D(item.unit_price)
                    if variant and item.variant_id is None:
                        price += D(variant.price_adjustment)
    return money(price)


def resolve_unit_cost(product: Product, variant: ProductVariant | None) -> Decimal:
    cost = D(product.cost_price)
    if variant:
        cost += D(variant.cost_adjustment)
    return money(cost)


def calculate_line(
    quantity: int,
    unit_price: Decimal,
    unit_cost: Decimal,
    discount_percent: Decimal,
    is_freebie: bool = False,
) -> dict:
    qty = max(int(quantity or 0), 0)
    disc = pct(discount_percent)
    if disc < 0:
        disc = ZERO
    if disc > 100:
        disc = D(100)
    if is_freebie:
        disc = D(100)
    gross = money(D(unit_price) * qty)
    discount_amount = money(gross * disc / D(100))
    net_amount = money(gross - discount_amount)
    total_cost = money(D(unit_cost) * qty)
    gross_profit = money(net_amount - total_cost)
    margin_percent = pct(safe_div(gross_profit, net_amount) * D(100))
    return {
        "quantity": qty,
        "unit_price": money(unit_price),
        "unit_cost": money(unit_cost),
        "discount_percent": disc,
        "discount_amount": discount_amount,
        "net_amount": net_amount,
        "total_cost": total_cost,
        "gross_profit": gross_profit,
        "margin_percent": margin_percent,
        "gross": gross,
    }


def calculate_totals(lines: list[dict], shipping_total: Decimal = ZERO, tax_percent: Decimal = D(18)) -> dict:
    subtotal = money(sum((ln["gross"] for ln in lines), ZERO))
    discount_total = money(sum((ln["discount_amount"] for ln in lines), ZERO))
    cost_total = money(sum((ln["total_cost"] for ln in lines), ZERO))
    net = money(subtotal - discount_total)
    shipping = money(shipping_total)
    taxable = money(net + shipping)
    tax_total = money(taxable * D(tax_percent) / D(100))
    total = money(taxable + tax_total)
    gross_profit = money(net - cost_total)
    gross_margin_percent = pct(safe_div(gross_profit, net) * D(100))
    return {
        "subtotal": subtotal,
        "discount_total": discount_total,
        "tax_total": tax_total,
        "shipping_total": shipping,
        "total": total,
        "cost_total": cost_total,
        "gross_profit": gross_profit,
        "gross_margin_percent": gross_margin_percent,
        "net_revenue": net,
        "tax_percent": pct(tax_percent),
    }
