from collections import defaultdict
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.core.exceptions import AppError
from app.models.catalog import Product
from app.models.customer import Customer
from app.models.enums import ProductType, QuoteStatus
from app.models.fulfillment import Backorder, FulfillmentAllocation, Inventory, Warehouse
from app.models.quote import Quote, QuoteLine
from app.utils.money import D, money, ZERO

# City-to-city shipping cost (INR) for a typical parcel
SHIPPING_MATRIX = {
    ("Ahmedabad", "Ahmedabad"): 80,
    ("Mumbai", "Mumbai"): 80,
    ("Bangalore", "Bangalore"): 80,
    ("Ahmedabad", "Mumbai"): 250,
    ("Mumbai", "Ahmedabad"): 250,
    ("Ahmedabad", "Bangalore"): 450,
    ("Bangalore", "Ahmedabad"): 450,
    ("Mumbai", "Bangalore"): 400,
    ("Bangalore", "Mumbai"): 400,
}

DELIVERY_DAYS = {
    ("Ahmedabad", "Ahmedabad"): 1,
    ("Mumbai", "Mumbai"): 1,
    ("Bangalore", "Bangalore"): 1,
    ("Ahmedabad", "Mumbai"): 2,
    ("Mumbai", "Ahmedabad"): 2,
    ("Ahmedabad", "Bangalore"): 4,
    ("Bangalore", "Ahmedabad"): 4,
    ("Mumbai", "Bangalore"): 3,
    ("Bangalore", "Mumbai"): 3,
}


def _ship_cost(from_city: str, to_city: str, handling: Decimal, db=None) -> Decimal:
    from app.services.settings import shipping_base

    base = shipping_base(db, from_city, to_city)
    return money(D(base) + D(handling))


def _days(from_city: str, to_city: str, lead: int) -> int:
    return DELIVERY_DAYS.get((from_city, to_city), 5) + max(lead - 2, 0)


def _physical_lines(lines: list[QuoteLine]) -> list[QuoteLine]:
    out = []
    for ln in lines:
        if ln.product and ln.product.product_type in (ProductType.ONE_TIME,) and not ln.is_freebie:
            # services/subscriptions don't ship
            if ln.product.category and ln.product.category.kind.value in ("SERVICE", "SUBSCRIPTION", "SOFTWARE"):
                continue
            out.append(ln)
        elif ln.product and ln.product.product_type == ProductType.ONE_TIME:
            out.append(ln)
    return out


class WarehouseAllocationService:
    def snapshot_inventory(self, db: Session) -> list[Inventory]:
        return db.query(Inventory).all()

    def current_plan(self, db: Session, quote: Quote, customer: Customer) -> dict:
        allocs = [a for a in quote.allocations if not a.is_recommended]
        if not allocs:
            allocs = self._greedy_allocate(db, quote, customer, persist=False)
            return self._summarize(db, quote, customer, allocs, recommended=False, persist=False)
        return self._summarize(db, quote, customer, allocs, recommended=False, persist=False)

    def optimize(self, db: Session, quote: Quote, customer: Customer, persist_recommended: bool = True) -> dict:
        current = self.current_plan(db, quote, customer)
        recommended_allocs = self._optimize_allocate(db, quote, customer)
        recommended = self._summarize(db, quote, customer, recommended_allocs, recommended=True, persist=persist_recommended)
        return {
            "current": current,
            "recommended": recommended,
            "savings": float(money(D(current["shipping_cost"]) - D(recommended["shipping_cost"]))),
            "shipment_change": recommended["shipments"] - current["shipments"],
        }

    def apply_recommended(self, db: Session, quote: Quote) -> dict:
        rec = [a for a in quote.allocations if a.is_recommended]
        if not rec:
            raise ValueError("No recommended plan to apply")
        for a in list(quote.allocations):
            if not a.is_recommended:
                db.delete(a)
        for a in rec:
            a.is_recommended = False
        db.flush()
        quote.shipment_count = len({a.warehouse_id for a in rec})
        quote.shipping_total = money(sum((D(a.shipping_cost) for a in rec), ZERO))
        return {"shipments": quote.shipment_count, "shipping_total": float(quote.shipping_total)}

    def availability(self, db: Session, quote: Quote) -> list[dict]:
        warehouses = db.query(Warehouse).order_by(Warehouse.name).all()
        out = []
        for line in quote.lines:
            if not self._needs_stock(line):
                continue
            options = []
            for wh in warehouses:
                inv = self._inv(db, wh.id, line.product_id, line.variant_id)
                free = max((inv.available_qty - inv.reserved_qty) if inv else 0, 0)
                options.append(
                    {
                        "warehouse_id": wh.id,
                        "name": wh.name,
                        "city": wh.city,
                        "free": free,
                        "available_qty": inv.available_qty if inv else 0,
                        "reserved_qty": inv.reserved_qty if inv else 0,
                    }
                )
            out.append(
                {
                    "product_id": line.product_id,
                    "line_id": line.id,
                    "product": line.product.name if line.product else line.description,
                    "quantity": line.quantity,
                    "warehouses": options,
                }
            )
        return out

    def queue(self, db: Session) -> list[dict]:
        quotes = (
            db.query(Quote)
            .options(
                joinedload(Quote.customer),
                joinedload(Quote.sales_rep),
                selectinload(Quote.backorders),
            )
            .filter(
                Quote.status.in_(
                    [QuoteStatus.APPROVED, QuoteStatus.NEGOTIATING, QuoteStatus.PENDING_APPROVAL, QuoteStatus.CONFIRMED]
                )
            )
            .order_by(Quote.updated_at.desc())
            .limit(40)
            .all()
        )
        items = []
        for q in quotes:
            bos = [b for b in (q.backorders or []) if (b.backorder_qty or 0) > 0]
            bo_qty = sum(int(b.backorder_qty or 0) for b in bos)
            if q.shipment_count <= 1 and bo_qty <= 0 and q.status == QuoteStatus.CONFIRMED:
                continue
            items.append(
                {
                    "id": q.id,
                    "quote_id": q.id,
                    "quote_number": q.quote_number,
                    "title": q.title,
                    "customer": q.customer.name if q.customer else None,
                    "sales_rep": q.sales_rep.name if q.sales_rep else None,
                    "status": q.status.value,
                    "shipments": q.shipment_count,
                    "shipping_total": float(q.shipping_total or 0),
                    "backorder_qty": bo_qty,
                    "href": f"/quotes/{q.id}?tab=Fulfill",
                }
            )
        return items

    def manual_allocate(self, db: Session, quote: Quote, customer: Customer, items: list[dict]) -> dict:
        if quote.status in (QuoteStatus.CONFIRMED, QuoteStatus.CANCELLED, QuoteStatus.REJECTED):
            raise AppError("QUOTE_LOCKED", "Fulfillment cannot be changed after confirmation.")
        need: dict[int, int] = {}
        lines_by_pid: dict[int, QuoteLine] = {}
        for line in quote.lines:
            if not self._needs_stock(line):
                continue
            need[line.product_id] = need.get(line.product_id, 0) + line.quantity
            lines_by_pid[line.product_id] = line
        assigned: dict[int, int] = defaultdict(int)
        dest = customer.city or "Ahmedabad"
        new_allocs: list[FulfillmentAllocation] = []
        for item in items:
            pid = int(item["product_id"])
            wid = int(item["warehouse_id"])
            qty = int(item["quantity"])
            if pid not in need:
                raise AppError("VALIDATION_ERROR", "Product is not a stocked line on this quote.")
            assigned[pid] += qty
            if assigned[pid] > need[pid]:
                raise AppError("VALIDATION_ERROR", "Allocated quantity exceeds the quoted quantity.")
            wh = db.get(Warehouse, wid)
            if not wh:
                raise AppError("NOT_FOUND", "Warehouse not found.", 404)
            inv = self._inv(db, wid, pid, lines_by_pid[pid].variant_id)
            free = max((inv.available_qty - inv.reserved_qty) if inv else 0, 0)
            take = min(qty, free)
            bo = qty - take
            line = lines_by_pid[pid]
            if take:
                new_allocs.append(self._make_alloc(quote, line, wh, take, dest, False, False))
            if bo:
                new_allocs.append(self._make_alloc(quote, line, wh, bo, dest, True, False))
        warehouses = db.query(Warehouse).all()
        fallback = warehouses[0] if warehouses else None
        for pid, qty_need in need.items():
            leftover = qty_need - assigned[pid]
            if leftover > 0 and fallback:
                new_allocs.append(self._make_alloc(quote, lines_by_pid[pid], fallback, leftover, dest, True, False))
        db.query(FulfillmentAllocation).filter(
            FulfillmentAllocation.quote_id == quote.id, FulfillmentAllocation.is_recommended.is_(False)
        ).delete()
        for a in new_allocs:
            db.add(a)
        db.flush()
        summary = self._summarize(db, quote, customer, new_allocs, recommended=False, persist=True)
        quote.shipment_count = summary["shipments"]
        quote.shipping_total = money(summary["shipping_cost"])
        quote.delivery_risk_score = D(summary["delivery_risk"])
        return summary

    def consolidate_backorders(self, db: Session, quote: Quote, customer: Customer) -> dict:
        """Re-run allocation against current free stock so newly available inventory fills backorders."""
        if quote.status in (QuoteStatus.CONFIRMED, QuoteStatus.CANCELLED, QuoteStatus.REJECTED):
            raise AppError("QUOTE_LOCKED", "Fulfillment cannot be changed after confirmation.")
        return self.persist_initial(db, quote, customer)

    def persist_initial(self, db: Session, quote: Quote, customer: Customer) -> dict:
        db.query(FulfillmentAllocation).filter(
            FulfillmentAllocation.quote_id == quote.id, FulfillmentAllocation.is_recommended.is_(False)
        ).delete()
        db.query(Backorder).filter(Backorder.quote_id == quote.id).delete()
        allocs = self._greedy_allocate(db, quote, customer, persist=True)
        summary = self._summarize(db, quote, customer, allocs, recommended=False, persist=True)
        quote.shipment_count = summary["shipments"]
        quote.shipping_total = money(summary["shipping_cost"])
        quote.delivery_risk_score = D(summary["delivery_risk"])
        return summary

    def _greedy_allocate(self, db: Session, quote: Quote, customer: Customer, persist: bool) -> list[FulfillmentAllocation]:
        """First-fit across warehouses sorted by city proximity — often splits shipments (demo-friendly)."""
        warehouses = db.query(Warehouse).all()
        dest = customer.city or "Ahmedabad"
        # Scarcity-first (farther/smaller DCs first) so the current plan is split and
        # the optimizer has a visible consolidation story.
        warehouses.sort(key=lambda w: w.city, reverse=True)
        allocs: list[FulfillmentAllocation] = []
        for line in quote.lines:
            if not self._needs_stock(line):
                continue
            remaining = line.quantity
            for wh in warehouses:
                if remaining <= 0:
                    break
                inv = self._inv(db, wh.id, line.product_id, line.variant_id)
                free = max((inv.available_qty - inv.reserved_qty) if inv else 0, 0)
                take = min(free, remaining)
                if take <= 0:
                    continue
                remaining -= take
                allocs.append(self._make_alloc(quote, line, wh, take, dest, backorder=False, recommended=False))
            if remaining > 0:
                # backorder against nearest warehouse
                wh = warehouses[0] if warehouses else None
                if wh:
                    allocs.append(self._make_alloc(quote, line, wh, remaining, dest, backorder=True, recommended=False))
        if persist:
            for a in allocs:
                db.add(a)
            db.flush()
        return allocs

    def _optimize_allocate(self, db: Session, quote: Quote, customer: Customer) -> list[FulfillmentAllocation]:
        """Minimize shipment count, then shipping cost, then delivery risk."""
        dest = customer.city or "Ahmedabad"
        warehouses = db.query(Warehouse).all()
        demand: dict[int, dict] = {}
        for line in quote.lines:
            if not self._needs_stock(line):
                continue
            slot = demand.setdefault(line.product_id, {"qty": 0, "line": line})
            slot["qty"] += line.quantity

        # Score warehouses by how much of total demand they can cover + inbound cost
        coverage = []
        for wh in warehouses:
            covered = 0
            total_need = 0
            for pid, slot in demand.items():
                inv = self._inv(db, wh.id, pid, slot["line"].variant_id)
                free = max((inv.available_qty - inv.reserved_qty) if inv else 0, 0)
                covered += min(free, slot["qty"])
                total_need += slot["qty"]
            cost = float(_ship_cost(wh.city, dest, ZERO, db))
            coverage.append((covered, -cost, wh.reliability_score, wh))
        coverage.sort(reverse=True)

        remaining = {pid: slot["qty"] for pid, slot in demand.items()}
        used: dict[int, dict[int, int]] = defaultdict(lambda: defaultdict(int))  # wh -> product -> qty
        back: dict[int, int] = defaultdict(int)

        for _, __, ___, wh in coverage:
            if all(v <= 0 for v in remaining.values()):
                break
            for pid, need in list(remaining.items()):
                if need <= 0:
                    continue
                inv = self._inv(db, wh.id, pid, demand[pid]["line"].variant_id)
                already = used[wh.id][pid]
                free = max(((inv.available_qty - inv.reserved_qty) if inv else 0) - already, 0)
                take = min(free, need)
                if take > 0:
                    used[wh.id][pid] += take
                    remaining[pid] -= take
        for pid, need in remaining.items():
            if need > 0:
                back[pid] += need
                # park backorder on highest-coverage warehouse
                wh = coverage[0][3] if coverage else warehouses[0]
                used[wh.id][pid] += need

        allocs: list[FulfillmentAllocation] = []
        for wh_id, products in used.items():
            wh = next(w for w in warehouses if w.id == wh_id)
            for pid, qty in products.items():
                line = demand[pid]["line"]
                is_bo = back.get(pid, 0) > 0 and qty > 0
                # only last remainder is backorder
                bo_qty = min(back.get(pid, 0), qty)
                ship_qty = qty - bo_qty
                if ship_qty:
                    allocs.append(self._make_alloc(quote, line, wh, ship_qty, dest, False, True))
                if bo_qty:
                    allocs.append(self._make_alloc(quote, line, wh, bo_qty, dest, True, True))
                    back[pid] -= bo_qty
        return allocs

    def _summarize(
        self,
        db: Session,
        quote: Quote,
        customer: Customer,
        allocs: list[FulfillmentAllocation],
        recommended: bool,
        persist: bool,
    ) -> dict:
        dest = customer.city or "Ahmedabad"
        by_wh: dict[int, dict] = {}
        shipping = ZERO
        backorder_qty = 0
        requested = 0
        promised = quote.promised_delivery_date
        max_days = 0
        for a in allocs:
            requested += a.quantity
            wh = a.warehouse or db.get(Warehouse, a.warehouse_id)
            slot = by_wh.setdefault(
                a.warehouse_id,
                {"warehouse_id": a.warehouse_id, "name": wh.name if wh else "?", "city": wh.city if wh else "?", "lines": [], "qty": 0},
            )
            prod = a.product or db.get(Product, a.product_id)
            slot["lines"].append(
                {
                    "product": prod.name if prod else str(a.product_id),
                    "product_id": a.product_id,
                    "quantity": a.quantity,
                    "is_backorder": a.is_backorder,
                    "shipping_cost": float(a.shipping_cost),
                    "delivery_days": a.delivery_days,
                }
            )
            slot["qty"] += a.quantity
            if a.is_backorder:
                backorder_qty += a.quantity
            else:
                shipping += D(a.shipping_cost)
            max_days = max(max_days, a.delivery_days)

        # shipping is per warehouse (one shipment), not per line
        shipment_cost = ZERO
        for wh_id, slot in by_wh.items():
            wh = db.get(Warehouse, wh_id)
            if wh:
                shipment_cost += _ship_cost(wh.city, dest, wh.handling_cost, db)
        shipments = len(by_wh)
        expected_days = max_days if max_days else 3
        delivery_risk = 0
        if backorder_qty:
            delivery_risk += 40
        if shipments > 2:
            delivery_risk += 15 * (shipments - 2)
        if expected_days > 5:
            delivery_risk += 10

        cause = None
        rec = None
        if backorder_qty:
            cause = f"Insufficient stock: {backorder_qty} units backordered."
            rec = "Split remaining units from the next-best warehouse or offer a substitute."
        elif shipments > 2:
            cause = f"Plan uses {shipments} warehouses."
            rec = "Consolidate into fewer warehouses to cut shipping and delivery risk."

        if persist and recommended:
            db.query(FulfillmentAllocation).filter(
                FulfillmentAllocation.quote_id == quote.id, FulfillmentAllocation.is_recommended.is_(True)
            ).delete()
            for a in allocs:
                a.is_recommended = True
                db.add(a)
            db.flush()

        # backorder rows
        backorders = []
        if persist and not recommended:
            db.query(Backorder).filter(Backorder.quote_id == quote.id).delete()
        grouped = defaultdict(lambda: {"req": 0, "bo": 0, "wh": None, "line": None, "product_id": None})
        for a in allocs:
            g = grouped[a.product_id]
            g["req"] += a.quantity
            g["product_id"] = a.product_id
            g["line"] = a.quote_line_id
            g["wh"] = a.warehouse_id
            if a.is_backorder:
                g["bo"] += a.quantity
        for pid, g in grouped.items():
            if g["bo"] <= 0:
                continue
            inv = self._inv(db, g["wh"], pid, None)
            item = {
                "product_id": pid,
                "requested_qty": g["req"],
                "available_qty": g["req"] - g["bo"],
                "backorder_qty": g["bo"],
                "expected_replenishment": str(inv.expected_replenishment) if inv and inv.expected_replenishment else None,
                "alternative_warehouse": self._alt_warehouse(db, pid, g["wh"]),
            }
            backorders.append(item)
            if persist and not recommended:
                db.add(
                    Backorder(
                        quote_id=quote.id,
                        quote_line_id=g["line"],
                        product_id=pid,
                        warehouse_id=g["wh"],
                        requested_qty=g["req"],
                        available_qty=g["req"] - g["bo"],
                        backorder_qty=g["bo"],
                        expected_replenishment=inv.expected_replenishment if inv else None,
                    )
                )

        return {
            "warehouses": list(by_wh.values()),
            "shipments": shipments,
            "shipping_cost": float(money(shipment_cost)),
            "backorder_qty": backorder_qty,
            "requested_qty": requested,
            "delivery_days": expected_days,
            "delivery_risk": min(delivery_risk, 100),
            "promised": str(promised) if promised else None,
            "expected": expected_days,
            "cause": cause,
            "recommendation": rec,
            "backorders": backorders,
        }

    def _needs_stock(self, line: QuoteLine) -> bool:
        if not line.product:
            return False
        if line.product.product_type != ProductType.ONE_TIME:
            return False
        if line.product.category and line.product.category.kind.value in ("SERVICE", "SUBSCRIPTION", "SOFTWARE"):
            return False
        return True

    def _inv(self, db: Session, warehouse_id: int, product_id: int, variant_id: int | None) -> Inventory | None:
        q = db.query(Inventory).filter(Inventory.warehouse_id == warehouse_id, Inventory.product_id == product_id)
        if variant_id:
            q = q.filter(Inventory.variant_id == variant_id)
        else:
            q = q.filter(Inventory.variant_id.is_(None))
        return q.first()

    def _make_alloc(self, quote, line, warehouse, qty, dest, backorder, recommended, db=None) -> FulfillmentAllocation:
        return FulfillmentAllocation(
            quote_id=quote.id,
            quote_line_id=line.id if line.id else None,
            warehouse_id=warehouse.id,
            product_id=line.product_id,
            quantity=qty,
            shipping_cost=_ship_cost(warehouse.city, dest, warehouse.handling_cost, db) if not backorder else ZERO,
            delivery_days=_days(warehouse.city, dest, warehouse.avg_lead_days) + (7 if backorder else 0),
            is_backorder=backorder,
            is_recommended=recommended,
        )

    def _alt_warehouse(self, db: Session, product_id: int, current_wh: int | None) -> str | None:
        rows = (
            db.query(Inventory)
            .filter(Inventory.product_id == product_id, Inventory.available_qty - Inventory.reserved_qty > 0)
            .all()
        )
        for r in rows:
            if r.warehouse_id != current_wh:
                return r.warehouse.name if r.warehouse else None
        return None
