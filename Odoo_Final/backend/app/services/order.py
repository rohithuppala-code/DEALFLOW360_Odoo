from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.events.bus import audit, event_bus, notify
from app.models.enums import (
    ApprovalStatus,
    BillingInterval,
    BillingType,
    EventType,
    InvoiceStatus,
    OrderStatus,
    ProductType,
    QuoteStatus,
    ReservationStatus,
    Severity,
    SubscriptionStatus,
    UserRole,
)
from app.models.fulfillment import Inventory, InventoryReservation
from app.models.ops import Order
from app.models.quote import Quote
from app.models.user import User
from app.services.billing import BillingService
from app.services.quote import quote_engine
from app.utils.money import D, money

billing_svc = BillingService()


class OrderConfirmationService:
    def confirm(self, db: Session, quote: Quote, user: User, admin_override: bool = False) -> Order:
        if quote.status == QuoteStatus.CONFIRMED:
            raise AppError("ALREADY_CONFIRMED", "This quote is already confirmed.")
        if quote.status in (QuoteStatus.CANCELLED, QuoteStatus.REJECTED):
            raise AppError("QUOTE_LOCKED", "This quote cannot be confirmed.")
        if quote.approval_status != ApprovalStatus.APPROVED and not (
            admin_override and user.role == UserRole.ADMIN
        ):
            if quote.approval_status != ApprovalStatus.NOT_REQUIRED:
                raise AppError(
                    "APPROVAL_REQUIRED",
                    "Only approved quotes can be confirmed. Complete approval first or use an admin override.",
                )
        quote_engine.recalculate(db, quote)

        try:
            # lock inventory rows
            self._reserve(db, quote)
            order = Order(
                order_number=self._next_order_number(db),
                quote_id=quote.id,
                customer_id=quote.customer_id,
                status=OrderStatus.CONFIRMED,
                total=quote.total,
                confirmed_at=datetime.utcnow(),
            )
            db.add(order)
            db.flush()
            invoice = billing_svc.create_from_quote(db, quote, order)
            subs = billing_svc.create_subscriptions(db, quote)
            quote.status = QuoteStatus.CONFIRMED
            quote.confirmed_at = datetime.utcnow()
            event_bus.publish(
                EventType.ORDER_CONFIRMED,
                {
                    "quote_id": quote.id,
                    "actor_id": user.id,
                    "description": f"Order {order.order_number} confirmed · ₹{float(order.total):,.0f}",
                    "metadata": {"order_id": order.id, "invoice_id": invoice.id if invoice else None},
                },
                db,
            )
            event_bus.publish(
                EventType.INVENTORY_RESERVED,
                {"quote_id": quote.id, "actor_id": user.id, "description": "Inventory reserved across warehouses"},
                db,
            )
            if invoice:
                event_bus.publish(
                    EventType.INVOICE_CREATED,
                    {
                        "quote_id": quote.id,
                        "actor_id": user.id,
                        "description": f"Invoice {invoice.invoice_number} issued",
                    },
                    db,
                )
            for sub in subs:
                event_bus.publish(
                    EventType.SUBSCRIPTION_CREATED,
                    {
                        "quote_id": quote.id,
                        "actor_id": user.id,
                        "description": f"Subscription started ({sub.billing_interval.value})",
                    },
                    db,
                )
            notify(
                db,
                quote.sales_rep_id,
                "ORDER_CONFIRMED",
                f"{quote.quote_number} confirmed",
                f"Order {order.order_number} created. Invoice generated.",
                Severity.INFO,
                "order",
                order.id,
            )
            audit(db, user.id, "ORDER_CONFIRM", "order", order.id, new_value={"quote": quote.quote_number})
            db.flush()
            return order
        except AppError:
            db.rollback()
            raise
        except Exception as exc:
            db.rollback()
            raise AppError("CONFIRM_FAILED", f"Order confirmation failed and was rolled back. {exc}") from exc

    def _reserve(self, db: Session, quote: Quote) -> None:
        allocs = [a for a in quote.allocations if not a.is_recommended and not a.is_backorder]
        # group by warehouse+product
        from collections import defaultdict

        need: dict[tuple[int, int], int] = defaultdict(int)
        for a in allocs:
            need[(a.warehouse_id, a.product_id)] += a.quantity
        for (wh_id, pid), qty in need.items():
            inv = (
                db.query(Inventory)
                .filter(Inventory.warehouse_id == wh_id, Inventory.product_id == pid)
                .with_for_update()
                .first()
            )
            if not inv:
                raise AppError("INVENTORY_CONFLICT", "Inventory changed. Please recalculate fulfillment.")
            free = inv.available_qty - inv.reserved_qty
            if free < qty:
                raise AppError(
                    "INVENTORY_CONFLICT",
                    "Reservation failed. Inventory changed. Please recalculate fulfillment.",
                )
            inv.reserved_qty += qty
            db.add(
                InventoryReservation(
                    quote_id=quote.id,
                    warehouse_id=wh_id,
                    product_id=pid,
                    quantity=qty,
                    status=ReservationStatus.RESERVED,
                )
            )

    def _next_order_number(self, db: Session) -> str:
        year = datetime.utcnow().year
        prefix = f"SO-{year}-"
        last = (
            db.query(Order.order_number)
            .filter(Order.order_number.like(f"{prefix}%"))
            .order_by(Order.order_number.desc())
            .first()
        )
        n = int(last[0].split("-")[-1]) + 1 if last else 1
        return f"{prefix}{n:04d}"
