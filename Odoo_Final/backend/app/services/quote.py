from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload, selectinload

from app.core.exceptions import AppError
from app.core.permissions import is_customer
from app.events.bus import audit, event_bus
from app.services.access import customer_owns_quote
from app.services.settings import get_setting
from app.models.catalog import Product, ProductVariant
from app.models.customer import Customer
from app.models.enums import EventType, ProductType, QuoteStatus, UserRole
from app.models.governance import ApprovalRequest
from app.models.quote import Quote, QuoteLine
from app.models.user import User
from app.services.anomaly import AnomalyDetectionService
from app.services.approval import ApprovalRoutingService
from app.services.discount import blended_exceptions, evaluate_line_discount, load_discount_rules
from app.services.fulfillment import WarehouseAllocationService
from app.services.health import compute_health
from app.services.margin import MarginGuardianService
from app.services.pricing import calculate_line, calculate_totals, resolve_unit_cost, resolve_unit_price
from app.services.risk import load_weights, persist_factors, score_deal
from app.utils.money import D, money, pct, safe_div, ZERO

approval_svc = ApprovalRoutingService()
fulfillment_svc = WarehouseAllocationService()
margin_svc = MarginGuardianService()
anomaly_svc = AnomalyDetectionService()


def next_quote_number(db: Session) -> str:
    year = datetime.utcnow().year
    prefix = f"Q-{year}-"
    last = (
        db.query(Quote.quote_number)
        .filter(Quote.quote_number.like(f"{prefix}%"))
        .order_by(Quote.quote_number.desc())
        .first()
    )
    n = 1
    if last:
        try:
            n = int(last[0].split("-")[-1]) + 1
        except ValueError:
            n = 1
    return f"{prefix}{n:04d}"


def load_quote(db: Session, quote_id: int) -> Quote:
    quote = (
        db.query(Quote)
        .options(
            joinedload(Quote.customer).joinedload(Customer.tier),
            joinedload(Quote.sales_rep),
            selectinload(Quote.lines).options(
                joinedload(QuoteLine.product).joinedload(Product.category),
                joinedload(QuoteLine.variant),
            ),
            selectinload(Quote.risk_factors),
            selectinload(Quote.approval_requests).selectinload(ApprovalRequest.steps),
        )
        .filter(Quote.id == quote_id)
        .first()
    )
    if not quote:
        raise AppError("NOT_FOUND", "Quote not found.", 404)
    return quote


def assert_quote_access(user: User, quote: Quote) -> None:
    if user.role == UserRole.ADMIN:
        return
    if is_customer(user):
        if not customer_owns_quote(user, quote):
            raise AppError("FORBIDDEN", "You cannot access this quote.", 403)
        if not quote.sent_to_customer_at and quote.status not in (QuoteStatus.APPROVED, QuoteStatus.NEGOTIATING, QuoteStatus.CONFIRMED):
            raise AppError("FORBIDDEN", "This quote has not been shared yet.", 403)
        return
    if user.role == UserRole.SALES_REP and quote.sales_rep_id != user.id:
        raise AppError("FORBIDDEN", "You can only access your own deals.", 403)


def _editable(quote: Quote) -> None:
    if quote.status in (QuoteStatus.CONFIRMED, QuoteStatus.CANCELLED):
        raise AppError("QUOTE_LOCKED", "This quote can no longer be edited.")


class QuoteEngine:
    def create(self, db: Session, user: User, payload: dict) -> Quote:
        customer = db.get(Customer, payload["customer_id"])
        if not customer:
            raise AppError("NOT_FOUND", "Customer not found.", 404)
        quote = Quote(
            quote_number=payload.get("quote_number") or next_quote_number(db),
            customer_id=customer.id,
            sales_rep_id=payload.get("sales_rep_id") or user.id,
            status=QuoteStatus.DRAFT,
            currency="INR",
            payment_terms=payload.get("payment_terms") or customer.payment_terms,
            notes=payload.get("notes"),
            title=payload.get("title") or f"{customer.name} deal",
            expires_at=payload.get("expires_at") or (date.today() + timedelta(days=21)),
            promised_delivery_date=payload.get("promised_delivery_date") or (date.today() + timedelta(days=14)),
            tax_percent=D(payload["tax_percent"] if payload.get("tax_percent") is not None else get_setting(db, "billing.default_tax_percent", 18)),
        )
        db.add(quote)
        db.flush()
        order_disc = D(payload.get("order_discount_percent") or 0)
        for line in payload.get("lines") or []:
            raw = dict(line)
            if order_disc:
                raw["discount_percent"] = min(100, float(raw.get("discount_percent") or 0) + float(order_disc))
            self._upsert_line(db, quote, raw)
        self.recalculate(db, quote)
        fulfillment_svc.persist_initial(db, quote, customer)
        self.recalculate(db, quote)  # shipping now known
        event_bus.publish(
            EventType.QUOTE_CREATED,
            {"quote_id": quote.id, "actor_id": user.id, "description": f"Quote {quote.quote_number} created"},
            db,
        )
        audit(db, user.id, "QUOTE_CREATE", "quote", quote.id, new_value={"number": quote.quote_number})
        db.flush()
        return quote

    def update(self, db: Session, quote: Quote, user: User, payload: dict) -> Quote:
        _editable(quote)
        material = False
        for field in ("payment_terms", "notes", "title", "expires_at", "promised_delivery_date"):
            if field in payload and payload[field] is not None:
                if field == "payment_terms" and quote.payment_terms != payload[field]:
                    material = True
                setattr(quote, field, payload[field])
        if "lines" in payload or payload.get("order_discount_percent") is not None:
            material = True
            existing = {ln.id: ln for ln in quote.lines}
            keep = set()
            order_disc = D(payload.get("order_discount_percent") or 0)
            raw_lines = payload.get("lines")
            if raw_lines is None:
                raw_lines = [
                    {
                        "id": ln.id,
                        "product_id": ln.product_id,
                        "quantity": ln.quantity,
                        "discount_percent": float(ln.discount_percent),
                        "variant_id": ln.variant_id,
                        "warehouse_id": ln.warehouse_id,
                        "subscription_plan_id": ln.subscription_plan_id,
                    }
                    for ln in quote.lines
                ]
            for raw in raw_lines:
                raw = dict(raw)
                if order_disc:
                    raw["discount_percent"] = min(100, float(raw.get("discount_percent") or 0) + float(order_disc))
                line = self._upsert_line(db, quote, raw)
                keep.add(line.id)
            if payload.get("lines") is not None:
                for lid, ln in existing.items():
                    if lid not in keep:
                        db.delete(ln)
            db.flush()
        self.recalculate(db, quote)
        fulfillment_svc.persist_initial(db, quote, quote.customer)
        self.recalculate(db, quote)
        ctx = self._approval_context(quote, self._last_intel)
        if material:
            quote.last_material_change_at = datetime.utcnow()
            approval_svc.invalidate_if_material(db, quote, ctx, user)
        event_bus.publish(
            EventType.QUOTE_UPDATED,
            {"quote_id": quote.id, "actor_id": user.id, "description": f"Quote {quote.quote_number} updated"},
            db,
        )
        db.flush()
        return quote

    def update_line_discount(self, db: Session, quote: Quote, user: User, line_id: int, discount_percent: Decimal) -> Quote:
        return self.update_line(db, quote, user, line_id, discount_percent=discount_percent)

    def update_line(
        self,
        db: Session,
        quote: Quote,
        user: User,
        line_id: int,
        quantity: int | None = None,
        discount_percent: Decimal | None = None,
    ) -> Quote:
        _editable(quote)
        line = next((l for l in quote.lines if l.id == line_id), None)
        if not line:
            raise AppError("NOT_FOUND", "Line not found.", 404)
        old_disc = float(line.discount_percent)
        old_qty = line.quantity
        material = False
        if quantity is not None:
            qty = int(quantity)
            if qty <= 0:
                raise AppError("VALIDATION_ERROR", "Quantity must be greater than 0.")
            if qty != line.quantity:
                line.quantity = qty
                material = True
        if discount_percent is not None:
            disc = pct(discount_percent)
            if disc < 0 or disc > 100:
                raise AppError("VALIDATION_ERROR", "Discount must be between 0 and 100.")
            if disc != line.discount_percent:
                line.discount_percent = disc
                material = True
        self.recalculate(db, quote)
        if old_disc != float(line.discount_percent):
            event_bus.publish(
                EventType.DISCOUNT_CHANGED,
                {
                    "quote_id": quote.id,
                    "actor_id": user.id,
                    "description": f"{line.product.name if line.product else 'Line'} discount changed {old_disc:.0f}% → {float(line.discount_percent):.0f}%",
                    "metadata": {"from": old_disc, "to": float(line.discount_percent)},
                },
                db,
            )
            audit(
                db,
                user.id,
                "DISCOUNT_CHANGE",
                "quote",
                quote.id,
                old_value={"discount": old_disc},
                new_value={"discount": float(line.discount_percent)},
            )
        if old_qty != line.quantity:
            event_bus.publish(
                EventType.QUOTE_UPDATED,
                {
                    "quote_id": quote.id,
                    "actor_id": user.id,
                    "description": f"{line.product.name if line.product else 'Line'} quantity {old_qty} → {line.quantity}",
                    "metadata": {"from": old_qty, "to": line.quantity},
                },
                db,
            )
        if material:
            fulfillment_svc.persist_initial(db, quote, quote.customer)
            self.recalculate(db, quote)
            ctx = self._approval_context(quote, self._last_intel)
            approval_svc.invalidate_if_material(db, quote, ctx, user)
        db.flush()
        return quote

    def add_product(self, db: Session, quote: Quote, user: User, product_id: int, quantity: int = 1, discount_percent: float = 0) -> Quote:
        _editable(quote)
        product = db.get(Product, product_id)
        if not product:
            raise AppError("NOT_FOUND", "Product not found.", 404)
        self._upsert_line(
            db,
            quote,
            {"product_id": product_id, "quantity": quantity, "discount_percent": discount_percent},
        )
        self.recalculate(db, quote)
        fulfillment_svc.persist_initial(db, quote, quote.customer)
        self.recalculate(db, quote)
        event_bus.publish(
            EventType.LINE_ADDED,
            {"quote_id": quote.id, "actor_id": user.id, "description": f"Added {product.name}"},
            db,
        )
        db.flush()
        return quote

    def preview(self, db: Session, payload: dict) -> dict:
        customer = db.get(Customer, payload["customer_id"])
        if not customer:
            raise AppError("NOT_FOUND", "Customer not found.", 404)
        lines_in = [dict(ln) for ln in (payload.get("lines") or [])]
        order_disc = D(payload.get("order_discount_percent") or 0)
        if order_disc:
            for ln in lines_in:
                ln["discount_percent"] = min(100, float(ln.get("discount_percent") or 0) + float(order_disc))
        calc_lines, products = self._compute_lines(db, customer, lines_in)
        shipping = D(payload.get("shipping_total") or 0)
        tax = payload.get("tax_percent")
        if tax is None:
            tax = get_setting(db, "billing.default_tax_percent", 18)
        totals = calculate_totals(calc_lines, shipping, D(tax))
        intel = self._intelligence(db, customer, calc_lines, totals, products, payload, quote=None)
        from app.services.recommendation import RecommendationService

        recs = RecommendationService().for_product_ids(db, list(products.keys()), customer)
        return {
            "customer_id": customer.id,
            "lines": [_serialize_line(ln) for ln in calc_lines],
            "totals": _dec_to_float(totals),
            "recommendations": recs,
            **intel,
        }

    def recalculate(self, db: Session, quote: Quote) -> dict:
        customer = quote.customer or db.get(Customer, quote.customer_id)
        products: dict[int, Product] = {}
        calc_lines = []
        for line in quote.lines:
            product = line.product or db.get(Product, line.product_id)
            variant = line.variant or (db.get(ProductVariant, line.variant_id) if line.variant_id else None)
            if not product:
                continue
            products[product.id] = product
            unit_price = resolve_unit_price(db, product, variant, customer, line.quantity)
            unit_cost = resolve_unit_cost(product, variant)
            # preserve explicit unit_price if already set and product price list didn't change intent
            if line.unit_price and D(line.unit_price) > 0:
                unit_price = D(line.unit_price)
            computed = calculate_line(line.quantity, unit_price, unit_cost, D(line.discount_percent), line.is_freebie)
            line.unit_price = computed["unit_price"]
            line.unit_cost = computed["unit_cost"]
            line.discount_percent = computed["discount_percent"]
            line.discount_amount = computed["discount_amount"]
            line.net_amount = computed["net_amount"]
            line.total_cost = computed["total_cost"]
            line.gross_profit = computed["gross_profit"]
            line.margin_percent = computed["margin_percent"]
            line.description = line.description or product.name
            calc_lines.append({**computed, "product_id": product.id, "id": line.id, "product": product})
        totals = calculate_totals(calc_lines, D(quote.shipping_total or 0), D(quote.tax_percent or 18))
        for k, v in totals.items():
            if hasattr(quote, k):
                setattr(quote, k, v)
        intel = self._intelligence(db, customer, calc_lines, totals, products, {"payment_terms": quote.payment_terms}, quote)
        persist_factors(db, quote, intel["risk"])
        quote.deal_health_score = D(intel["health"]["score"])
        quote.risk_score = D(intel["risk"]["score"])
        self._last_intel = intel
        db.flush()
        intel["totals"] = _dec_to_float(totals)
        return intel

    def submit(self, db: Session, quote: Quote, user: User) -> Quote:
        _editable(quote)
        if not quote.lines:
            raise AppError("VALIDATION_ERROR", "Add at least one product before submitting.")
        intel = self.recalculate(db, quote)
        ctx = self._approval_context(quote, intel)
        req = approval_svc.submit(db, quote, user, ctx)
        if req is None:
            quote.status = QuoteStatus.APPROVED
            quote.approval_status = quote.approval_status
        db.flush()
        return quote

    def _upsert_line(self, db: Session, quote: Quote, raw: dict) -> QuoteLine:
        product = db.get(Product, raw["product_id"])
        if not product or not product.is_active:
            raise AppError("VALIDATION_ERROR", "Invalid or inactive product.")
        qty = int(raw.get("quantity") or 1)
        if qty <= 0:
            raise AppError("VALIDATION_ERROR", "Quantity must be greater than 0.")
        disc = D(raw.get("discount_percent") or 0)
        if disc < 0 or disc > 100:
            raise AppError("VALIDATION_ERROR", "Discount must be between 0 and 100.")
        if product.product_type == ProductType.SUBSCRIPTION and not (
            raw.get("subscription_plan_id") or product.subscription_plan_id
        ):
            raise AppError("VALIDATION_ERROR", f"{product.name} requires a subscription plan.")
        variant = db.get(ProductVariant, raw["variant_id"]) if raw.get("variant_id") else None
        line = None
        if raw.get("id"):
            line = db.get(QuoteLine, raw["id"])
        if line is None:
            line = QuoteLine(quote_id=quote.id, product_id=product.id)
            db.add(line)
        line.product_id = product.id
        line.variant_id = variant.id if variant else None
        line.quantity = qty
        line.discount_percent = disc
        line.warehouse_id = raw.get("warehouse_id")
        line.delivery_date = raw.get("delivery_date")
        line.subscription_plan_id = raw.get("subscription_plan_id") or product.subscription_plan_id
        line.is_freebie = bool(raw.get("is_freebie"))
        line.source_recommendation_id = raw.get("source_recommendation_id")
        unit_price = resolve_unit_price(db, product, variant, quote.customer, qty)
        if raw.get("unit_price") is not None:
            unit_price = D(raw["unit_price"])
        line.unit_price = unit_price
        line.unit_cost = resolve_unit_cost(product, variant)
        line.description = raw.get("description") or product.name
        db.flush()
        return line

    def _compute_lines(self, db: Session, customer: Customer, lines_in: list[dict]):
        rules_unused = load_discount_rules(db)
        products = {}
        calc = []
        for raw in lines_in:
            product = db.get(Product, raw["product_id"])
            if not product:
                raise AppError("VALIDATION_ERROR", "Invalid product on quote line.")
            products[product.id] = product
            variant = db.get(ProductVariant, raw["variant_id"]) if raw.get("variant_id") else None
            qty = int(raw.get("quantity") or 1)
            unit_price = resolve_unit_price(db, product, variant, customer, qty)
            if raw.get("unit_price") is not None:
                unit_price = D(raw["unit_price"])
            unit_cost = resolve_unit_cost(product, variant)
            computed = calculate_line(qty, unit_price, unit_cost, D(raw.get("discount_percent") or 0), bool(raw.get("is_freebie")))
            computed.update(
                {
                    "product_id": product.id,
                    "variant_id": variant.id if variant else None,
                    "product_name": product.name,
                    "sku": product.sku,
                    "product_type": product.product_type.value,
                    "category": product.category.name if product.category else None,
                }
            )
            calc.append(computed)
        return calc, products

    def _intelligence(self, db, customer, calc_lines, totals, products, payload, quote: Quote | None) -> dict:
        rules = load_discount_rules(db)
        evaluations = []
        for ln in calc_lines:
            product = products.get(ln["product_id"])
            evaluations.append(evaluate_line_discount(rules, customer, product, ln["discount_percent"]))
        blended = blended_exceptions(evaluations, totals["net_revenue"])
        deal_disc = pct(safe_div(totals["discount_total"], totals["subtotal"]) * D(100))
        negotiation_count = 0
        if quote:
            from app.models.enums import RequestStatus
            from app.models.negotiation import NegotiationRequest, Negotiation

            negotiation_count = (
                db.query(func.count(NegotiationRequest.id))
                .join(Negotiation, Negotiation.id == NegotiationRequest.negotiation_id)
                .filter(Negotiation.quote_id == quote.id, NegotiationRequest.status == RequestStatus.PENDING)
                .scalar()
                or 0
            )
        backorder_qty = sum(b.backorder_qty for b in (quote.backorders if quote else [])) if quote else 0
        requested_qty = sum(ln["quantity"] for ln in calc_lines if products[ln["product_id"]].product_type.value == "ONE_TIME")
        shipments = quote.shipment_count if quote else 1
        rep_avg = None
        hist_avg = None
        if quote:
            from sqlalchemy import func as f

            rep_avg = db.query(f.avg(Quote.discount_total / f.nullif(Quote.subtotal, 0) * 100)).filter(
                Quote.sales_rep_id == quote.sales_rep_id, Quote.id != quote.id
            ).scalar()
            hist_avg = db.query(f.avg(Quote.total)).filter(Quote.customer_id == customer.id, Quote.id != quote.id).scalar()
        weights = load_weights(db)
        risk = score_deal(
            discount_evaluations=evaluations,
            blended=blended,
            margin_percent=totals["gross_margin_percent"],
            customer_tier=customer.tier.name,
            customer_risk_multiplier=D(customer.tier.risk_multiplier),
            payment_terms=int(payload.get("payment_terms") or customer.payment_terms),
            shipment_count=shipments,
            backorder_qty=backorder_qty,
            requested_qty=requested_qty,
            negotiation_count=int(negotiation_count),
            rep_avg_discount=D(rep_avg) if rep_avg else D("8.5"),
            deal_discount_percent=deal_disc,
            deal_value=totals["total"],
            historical_avg_deal=D(hist_avg) if hist_avg else None,
            weights=weights,
        )
        guardian = margin_svc.analyze(calc_lines, products)
        age_days = 0
        pending_days = 0
        if quote and quote.created_at:
            age_days = (datetime.utcnow() - quote.created_at).days
            if quote.approval_requests:
                latest = max(quote.approval_requests, key=lambda r: r.created_at)
                if latest.status.value == "PENDING":
                    pending_days = (datetime.utcnow() - latest.created_at).days
        health = compute_health(
            margin_percent=totals["gross_margin_percent"],
            risk_score=D(risk["score"]),
            quote_age_days=age_days,
            approval_status=quote.approval_status if quote else None,  # type: ignore
            approval_pending_days=pending_days,
            inventory_ok=backorder_qty == 0,
            backorder_qty=backorder_qty,
            negotiation_open=negotiation_count > 0,
            customer_engaged=bool(quote.sent_to_customer_at) if quote else False,
            payment_terms=int(payload.get("payment_terms") or customer.payment_terms),
        )
        from app.models.enums import ApprovalStatus as AS

        if not quote:
            from app.models.enums import ApprovalStatus as AS2

            health = compute_health(
                margin_percent=totals["gross_margin_percent"],
                risk_score=D(risk["score"]),
                quote_age_days=0,
                approval_status=AS2.NOT_REQUIRED,
                approval_pending_days=0,
                inventory_ok=True,
                backorder_qty=0,
                negotiation_open=False,
                customer_engaged=False,
                payment_terms=int(payload.get("payment_terms") or customer.payment_terms),
            )
        dummy = quote
        approval_ctx = {
            "has_discount_exception": blended["has_exceptions"],
            "max_exception": blended["max_exception_points"],
        }
        approval = None
        if quote:
            approval = approval_svc.evaluate(db, quote, approval_ctx)
        else:
            # lightweight: construct a throwaway evaluation using totals on a shim
            approval = {
                "required": blended["has_exceptions"] or float(totals["gross_margin_percent"]) < 18 or risk["score"] > 70,
                "reasons": [],
                "roles": [],
                "steps": [],
            }
            if blended["has_exceptions"]:
                approval["reasons"].append("Discount exceeds customer-tier policy.")
                approval["roles"].append("SALES_MANAGER")
            if float(totals["gross_margin_percent"]) < 18:
                approval["reasons"].append("Margin is below 18%.")
                approval["roles"].append("FINANCE")
            if risk["score"] > 70:
                approval["reasons"].append("Risk score exceeds 70.")
                approval["roles"].append("SALES_MANAGER")
            if risk["score"] > 85:
                approval["roles"].append("FINANCE")
            approval["required"] = bool(approval["roles"])
            approval["roles"] = list(dict.fromkeys(approval["roles"]))
        anomalies = []
        if quote:
            anomalies = anomaly_svc.detect_for_quote(db, quote, deal_disc)
        return {
            "risk": risk,
            "health": health,
            "discount": {
                "evaluations": [
                    {k: (float(v) if isinstance(v, Decimal) else v) for k, v in e.items()} for e in evaluations
                ],
                "blended": {
                    **blended,
                    "total_exception_points": float(blended["total_exception_points"]),
                    "max_exception_points": float(blended["max_exception_points"]),
                    "order_value": float(blended["order_value"]),
                    "evaluations": [
                        {k: (float(v) if isinstance(v, Decimal) else v) for k, v in e.items()}
                        for e in blended["evaluations"]
                    ],
                },
                "deal_discount_percent": float(deal_disc),
            },
            "margin_guardian": guardian,
            "approval_preview": approval,
            "anomalies": anomalies,
        }

    def _approval_context(self, quote: Quote, intel: dict | None) -> dict:
        intel = intel or getattr(self, "_last_intel", {}) or {}
        blended = (intel.get("discount") or {}).get("blended") or {}
        return {
            "has_discount_exception": blended.get("has_exceptions"),
            "max_exception": blended.get("max_exception_points") or 0,
        }

    _last_intel: dict | None = None


quote_engine = QuoteEngine()


def _dec_to_float(d: dict) -> dict:
    return {k: (float(v) if isinstance(v, Decimal) else v) for k, v in d.items()}


def _serialize_line(ln: dict) -> dict:
    out = {}
    for k, v in ln.items():
        if k in ("product",):
            continue
        out[k] = float(v) if isinstance(v, Decimal) else v
    return out
