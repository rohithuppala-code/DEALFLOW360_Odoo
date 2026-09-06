from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.events.bus import event_bus
from app.models.billing import Invoice, InvoiceLine, Payment, Subscription, SubscriptionPlan
from app.models.enums import (
    BillingInterval,
    BillingType,
    EventType,
    InvoiceStatus,
    PaymentStatus,
    ProductType,
    SubscriptionStatus,
)
from app.models.ops import Order
from app.models.quote import Quote
from app.utils.money import D, money, ZERO


INTERVAL_MONTHS = {
    BillingInterval.MONTHLY: 1,
    BillingInterval.QUARTERLY: 3,
    BillingInterval.YEARLY: 12,
}


def to_mrr(price: Decimal, interval: BillingInterval, qty: int, discount_percent: Decimal) -> Decimal:
    net = money(price * qty * (D(1) - D(discount_percent) / D(100)))
    months = INTERVAL_MONTHS.get(interval, 1)
    return money(net / D(months))


class BillingService:
    def create_from_quote(self, db: Session, quote: Quote, order: Order) -> Invoice | None:
        one_time = [ln for ln in quote.lines if ln.product and ln.product.product_type != ProductType.SUBSCRIPTION]
        recurring = [ln for ln in quote.lines if ln.product and ln.product.product_type == ProductType.SUBSCRIPTION]
        if not one_time and not recurring:
            return None
        # Invoice one-time now; first period of subscriptions also billed now (no trial unless plan.trial_days)
        invoice = Invoice(
            invoice_number=self._next_invoice_number(db),
            customer_id=quote.customer_id,
            quote_id=quote.id,
            order_id=order.id,
            status=InvoiceStatus.ISSUED,
            invoice_date=date.today(),
            due_date=date.today() + timedelta(days=quote.payment_terms or 30),
        )
        db.add(invoice)
        db.flush()
        subtotal = ZERO
        discount = ZERO
        for ln in one_time:
            db.add(
                InvoiceLine(
                    invoice_id=invoice.id,
                    product_id=ln.product_id,
                    description=ln.description or ln.product.name,
                    quantity=ln.quantity,
                    unit_price=ln.unit_price,
                    discount=ln.discount_amount,
                    amount=ln.net_amount,
                    billing_type=BillingType.ONE_TIME,
                )
            )
            subtotal += D(ln.unit_price) * ln.quantity
            discount += D(ln.discount_amount)
        for ln in recurring:
            db.add(
                InvoiceLine(
                    invoice_id=invoice.id,
                    product_id=ln.product_id,
                    description=f"{ln.product.name} (first period)",
                    quantity=ln.quantity,
                    unit_price=ln.unit_price,
                    discount=ln.discount_amount,
                    amount=ln.net_amount,
                    billing_type=BillingType.RECURRING,
                )
            )
            subtotal += D(ln.unit_price) * ln.quantity
            discount += D(ln.discount_amount)
        if quote.shipping_total:
            db.add(
                InvoiceLine(
                    invoice_id=invoice.id,
                    description="Shipping & handling",
                    quantity=1,
                    unit_price=quote.shipping_total,
                    discount=0,
                    amount=quote.shipping_total,
                    billing_type=BillingType.ONE_TIME,
                )
            )
            subtotal += D(quote.shipping_total)
        net = money(subtotal - discount)
        tax = money(net * D(quote.tax_percent or 18) / D(100))
        invoice.subtotal = money(subtotal)
        invoice.discount = money(discount)
        invoice.tax = tax
        invoice.total = money(net + tax)
        invoice.balance_due = invoice.total
        db.flush()
        return invoice

    def create_subscriptions(self, db: Session, quote: Quote) -> list[Subscription]:
        created = []
        for ln in quote.lines:
            if not ln.product or ln.product.product_type != ProductType.SUBSCRIPTION:
                continue
            plan = ln.subscription_plan or ln.product.subscription_plan
            if not plan:
                continue
            start = date.today()
            trial = plan.trial_days or 0
            next_bill = start + timedelta(days=trial if trial else 0)
            if trial:
                next_bill = start + timedelta(days=trial)
            else:
                next_bill = self._add_interval(start, plan.billing_interval)
            mrr = to_mrr(D(ln.unit_price), plan.billing_interval, ln.quantity, D(ln.discount_percent))
            sub = Subscription(
                customer_id=quote.customer_id,
                quote_id=quote.id,
                plan_id=plan.id,
                product_id=ln.product_id,
                status=SubscriptionStatus.TRIAL if trial else SubscriptionStatus.ACTIVE,
                start_date=start,
                billing_interval=plan.billing_interval,
                quantity=ln.quantity,
                unit_price=ln.unit_price,
                discount_percent=ln.discount_percent,
                next_billing_date=next_bill,
                mrr=mrr,
            )
            db.add(sub)
            created.append(sub)
        db.flush()
        return created

    def pay_invoice(self, db: Session, invoice: Invoice, amount: Decimal, method: str, user_id: int | None) -> Payment:
        if invoice.status in (InvoiceStatus.PAID, InvoiceStatus.VOID):
            raise AppError("INVALID_PAYMENT", "This invoice cannot accept payments.")
        amt = money(amount)
        if amt <= 0 or amt > D(invoice.balance_due) + D("0.05"):
            raise AppError("INVALID_PAYMENT", "Payment amount is invalid.")
        payment = Payment(
            invoice_id=invoice.id,
            amount=amt,
            payment_method=method or "BANK_TRANSFER",
            status=PaymentStatus.COMPLETED,
            paid_at=datetime.utcnow(),
        )
        db.add(payment)
        invoice.balance_due = money(D(invoice.balance_due) - amt)
        if invoice.balance_due <= 0:
            invoice.status = InvoiceStatus.PAID
            invoice.balance_due = ZERO
        else:
            invoice.status = InvoiceStatus.PARTIALLY_PAID
        if invoice.quote_id:
            event_bus.publish(
                EventType.PAYMENT_RECEIVED,
                {
                    "quote_id": invoice.quote_id,
                    "actor_id": user_id,
                    "description": f"Payment of ₹{float(amt):,.0f} received for {invoice.invoice_number}",
                },
                db,
            )
        db.flush()
        return payment

    def prorate(self, old_price: Decimal, new_price: Decimal, remaining_days: int, period_days: int = 30) -> dict:
        if period_days <= 0:
            period_days = 30
        remaining_days = max(0, remaining_days)
        unused_old = money(D(old_price) * D(remaining_days) / D(period_days))
        new_partial = money(D(new_price) * D(remaining_days) / D(period_days))
        adjustment = money(new_partial - unused_old)
        return {
            "old_price": float(money(old_price)),
            "new_price": float(money(new_price)),
            "remaining_days": remaining_days,
            "period_days": period_days,
            "credit": float(unused_old),
            "new_charge": float(new_partial),
            "prorated_adjustment": float(adjustment),
        }

    def change_plan(self, db: Session, sub: Subscription, new_plan: SubscriptionPlan, remaining_days: int) -> dict:
        pr = self.prorate(sub.unit_price, new_plan.price, remaining_days, self._period_days(sub.billing_interval, db))
        sub.plan_id = new_plan.id
        sub.unit_price = new_plan.price
        sub.billing_interval = new_plan.billing_interval
        sub.mrr = to_mrr(D(new_plan.price), new_plan.billing_interval, sub.quantity, D(sub.discount_percent))
        db.flush()
        return pr

    def apply_subscription_change(
        self,
        db: Session,
        sub: Subscription,
        *,
        new_plan: SubscriptionPlan | None,
        quantity: int | None,
        remaining_days: int | None,
        reason: str | None,
        user_id: int | None,
    ) -> dict:
        if sub.status in (SubscriptionStatus.CANCELLED, SubscriptionStatus.EXPIRED):
            raise AppError("INVALID_SUBSCRIPTION", "This subscription is no longer active.")
        days = remaining_days if remaining_days is not None else self._remaining_days(sub)
        old_price = money(D(sub.unit_price) * sub.quantity)
        if new_plan:
            pr = self.change_plan(db, sub, new_plan, days)
            new_price = money(D(new_plan.price) * (quantity or sub.quantity))
        else:
            new_price = old_price
            pr = self.prorate(old_price, new_price, days, self._period_days(sub.billing_interval, db))
        if quantity and quantity != sub.quantity:
            pr = self.prorate(
                money(D(sub.unit_price) * sub.quantity),
                money(D(sub.unit_price) * quantity),
                days,
                self._period_days(sub.billing_interval, db),
            )
            sub.quantity = quantity
            sub.mrr = to_mrr(D(sub.unit_price), sub.billing_interval, sub.quantity, D(sub.discount_percent))
        adj = D(pr["prorated_adjustment"])
        invoice = None
        credit = None
        desc = reason or (f"Plan change to {new_plan.name}" if new_plan else "Subscription change")
        if adj > 0:
            invoice = self._issue_charge(db, sub, adj, desc, user_id)
        elif adj < 0:
            credit = self.issue_credit_note(
                db,
                customer_id=sub.customer_id,
                amount=-adj,
                description=desc,
                quote_id=sub.quote_id,
                subscription_id=sub.id,
                user_id=user_id,
            )
        db.flush()
        return {"proration": pr, "invoice": self._invoice_brief(invoice) if invoice else None, "credit_note": self._invoice_brief(credit) if credit else None}

    def cancel_subscription(
        self,
        db: Session,
        sub: Subscription,
        remaining_days: int | None,
        reason: str | None,
        user_id: int | None,
    ) -> dict:
        if sub.status == SubscriptionStatus.CANCELLED:
            raise AppError("INVALID_SUBSCRIPTION", "Subscription is already cancelled.")
        days = remaining_days if remaining_days is not None else self._remaining_days(sub)
        from app.services.settings import get_setting

        cancel_cfg = get_setting(db, "billing.cancellation", {}) or {}
        period = self._period_days(sub.billing_interval, db)
        net = money(D(sub.unit_price) * sub.quantity * (D(1) - D(sub.discount_percent) / D(100)))
        unused = money(net * D(max(days, 0)) / D(period)) if period else ZERO
        if not cancel_cfg.get("credit_unused", True) or days < int(cancel_cfg.get("min_days") or 0):
            unused = ZERO
        credit = None
        if unused > 0:
            credit = self.issue_credit_note(
                db,
                customer_id=sub.customer_id,
                amount=unused,
                description=reason or f"Cancellation credit ({days} days unused)",
                quote_id=sub.quote_id,
                subscription_id=sub.id,
                user_id=user_id,
            )
        sub.status = SubscriptionStatus.CANCELLED
        sub.end_date = date.today()
        sub.next_billing_date = None
        db.flush()
        return {"credit": float(unused), "credit_note": self._invoice_brief(credit) if credit else None, "remaining_days": days}

    def issue_credit_note(
        self,
        db: Session,
        *,
        customer_id: int,
        amount,
        description: str,
        quote_id: int | None = None,
        subscription_id: int | None = None,
        user_id: int | None = None,
    ) -> Invoice:
        amt = money(amount)
        if amt <= 0:
            raise AppError("VALIDATION_ERROR", "Credit amount must be greater than zero.")
        open_inv = (
            db.query(Invoice)
            .filter(
                Invoice.customer_id == customer_id,
                Invoice.balance_due > 0,
                Invoice.status.in_([InvoiceStatus.ISSUED, InvoiceStatus.PARTIALLY_PAID, InvoiceStatus.OVERDUE]),
            )
            .order_by(Invoice.id.desc())
            .first()
        )
        applied = ZERO
        if open_inv:
            applied = money(min(amt, D(open_inv.balance_due)))
            open_inv.balance_due = money(D(open_inv.balance_due) - applied)
            if open_inv.balance_due <= 0:
                open_inv.status = InvoiceStatus.PAID
                open_inv.balance_due = ZERO
            else:
                open_inv.status = InvoiceStatus.PARTIALLY_PAID
        credit = Invoice(
            invoice_number=self._next_invoice_number(db),
            customer_id=customer_id,
            quote_id=quote_id,
            subscription_id=subscription_id,
            status=InvoiceStatus.PAID,
            invoice_date=date.today(),
            due_date=date.today(),
            subtotal=money(-amt),
            discount=ZERO,
            tax=ZERO,
            total=money(-amt),
            balance_due=ZERO,
        )
        db.add(credit)
        db.flush()
        db.add(
            InvoiceLine(
                invoice_id=credit.id,
                description=description,
                quantity=1,
                unit_price=money(-amt),
                discount=0,
                amount=money(-amt),
                billing_type=BillingType.PRORATION,
            )
        )
        if quote_id:
            event_bus.publish(
                EventType.INVOICE_CREATED,
                {
                    "quote_id": quote_id,
                    "actor_id": user_id,
                    "description": f"Credit note {credit.invoice_number} for ₹{float(amt):,.0f}"
                    + (f" (₹{float(applied):,.0f} applied to open invoice)" if applied else ""),
                },
                db,
            )
        db.flush()
        return credit

    def _issue_charge(self, db: Session, sub: Subscription, amount, description: str, user_id: int | None) -> Invoice:
        amt = money(amount)
        inv = Invoice(
            invoice_number=self._next_invoice_number(db),
            customer_id=sub.customer_id,
            quote_id=sub.quote_id,
            subscription_id=sub.id,
            status=InvoiceStatus.ISSUED,
            invoice_date=date.today(),
            due_date=date.today() + timedelta(days=15),
            subtotal=amt,
            discount=ZERO,
            tax=ZERO,
            total=amt,
            balance_due=amt,
        )
        db.add(inv)
        db.flush()
        db.add(
            InvoiceLine(
                invoice_id=inv.id,
                product_id=sub.product_id,
                description=description,
                quantity=1,
                unit_price=amt,
                discount=0,
                amount=amt,
                billing_type=BillingType.PRORATION,
            )
        )
        if sub.quote_id:
            event_bus.publish(
                EventType.INVOICE_CREATED,
                {"quote_id": sub.quote_id, "actor_id": user_id, "description": f"Proration invoice {inv.invoice_number}"},
                db,
            )
        db.flush()
        return inv

    def _remaining_days(self, sub: Subscription) -> int:
        if not sub.next_billing_date:
            return 0
        return max((sub.next_billing_date - date.today()).days, 0)

    def _period_days(self, interval: BillingInterval, db: Session | None = None) -> int:
        from app.services.settings import get_setting

        cfg = get_setting(db, "billing.proration", {}) or {}
        mapping = {
            BillingInterval.MONTHLY: int(cfg.get("monthly_days") or 30),
            BillingInterval.QUARTERLY: int(cfg.get("quarterly_days") or 90),
            BillingInterval.YEARLY: int(cfg.get("yearly_days") or 365),
        }
        return mapping.get(interval, 30)

    def _invoice_brief(self, inv: Invoice | None) -> dict | None:
        if not inv:
            return None
        return {
            "id": inv.id,
            "invoice_number": inv.invoice_number,
            "total": float(inv.total),
            "balance_due": float(inv.balance_due),
            "status": inv.status.value,
        }

    def schedule(self, sub: Subscription, periods: int = 6) -> list[str]:
        dates = []
        d = sub.next_billing_date
        for _ in range(periods):
            if not d:
                break
            dates.append(str(d))
            d = self._add_interval(d, sub.billing_interval)
        return dates

    def quote_billing_summary(self, quote: Quote) -> dict:
        one_time = ZERO
        recurring = ZERO
        mrr = ZERO
        items = []
        for ln in quote.lines:
            if not ln.product:
                continue
            if ln.product.product_type == ProductType.SUBSCRIPTION:
                plan = ln.subscription_plan or ln.product.subscription_plan
                interval = plan.billing_interval if plan else BillingInterval.MONTHLY
                recurring += D(ln.net_amount)
                mrr += to_mrr(D(ln.unit_price), interval, ln.quantity, D(ln.discount_percent))
                items.append(
                    {
                        "name": ln.product.name,
                        "type": "SUBSCRIPTION",
                        "amount": float(ln.net_amount),
                        "interval": interval.value,
                    }
                )
            else:
                one_time += D(ln.net_amount)
                items.append({"name": ln.product.name, "type": ln.product.product_type.value, "amount": float(ln.net_amount)})
        return {
            "one_time": float(money(one_time)),
            "recurring": float(money(recurring)),
            "mrr": float(money(mrr)),
            "arr": float(money(mrr * 12)),
            "shipping": float(quote.shipping_total or 0),
            "tax": float(quote.tax_total or 0),
            "total_due_today": float(quote.total or 0),
            "items": items,
        }

    def _next_invoice_number(self, db: Session) -> str:
        year = datetime.utcnow().year
        prefix = f"INV-{year}-"
        last = (
            db.query(Invoice.invoice_number)
            .filter(Invoice.invoice_number.like(f"{prefix}%"))
            .order_by(Invoice.invoice_number.desc())
            .first()
        )
        n = int(last[0].split("-")[-1]) + 1 if last else 1
        return f"{prefix}{n:04d}"

    def _add_interval(self, start: date, interval: BillingInterval) -> date:
        months = INTERVAL_MONTHS[interval]
        month = start.month - 1 + months
        year = start.year + month // 12
        month = month % 12 + 1
        day = min(start.day, 28)
        return date(year, month, day)
