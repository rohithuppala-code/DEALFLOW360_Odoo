from datetime import datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.events.bus import event_bus, notify
from app.models.catalog import Product
from app.models.enums import (
    EventType,
    NegotiationRequestType,
    NegotiationStatus,
    QuoteStatus,
    RequestStatus,
    Severity,
    UserRole,
)
from app.models.negotiation import Negotiation, NegotiationRequest
from app.models.quote import Quote, QuoteLine
from app.models.user import User
from app.services.discount import evaluate_line_discount, load_discount_rules
from app.services.pricing import calculate_line, calculate_totals
from app.services.quote import quote_engine
from app.utils.money import D, money, pct, ZERO


def mark_under_negotiation(quote: Quote) -> None:
    quote.negotiation_status = NegotiationStatus.OPEN
    if quote.status not in (QuoteStatus.CONFIRMED, QuoteStatus.CANCELLED, QuoteStatus.REJECTED):
        quote.status = QuoteStatus.NEGOTIATING


class NegotiationIntelligenceService:
    def ensure(self, db: Session, quote: Quote) -> Negotiation:
        n = (
            db.query(Negotiation)
            .filter(Negotiation.quote_id == quote.id, Negotiation.status.in_([NegotiationStatus.OPEN, NegotiationStatus.COUNTERED]))
            .order_by(Negotiation.id.desc())
            .first()
        )
        if n:
            mark_under_negotiation(quote)
            return n
        n = Negotiation(quote_id=quote.id, customer_id=quote.customer_id, status=NegotiationStatus.OPEN)
        db.add(n)
        db.flush()
        mark_under_negotiation(quote)
        return n

    def _notify_managers(self, db: Session, quote: Quote, actor: User, message: str) -> None:
        recipients: set[int] = set()
        if quote.sales_rep_id:
            recipients.add(quote.sales_rep_id)
        for manager in db.query(User).filter(User.role == UserRole.SALES_MANAGER, User.is_active.is_(True)).all():
            recipients.add(manager.id)
        for uid in recipients:
            if uid == actor.id:
                continue
            notify(
                db,
                uid,
                "NEGOTIATION",
                f"{quote.quote_number} under negotiation",
                message,
                Severity.HIGH,
                "quote",
                quote.id,
            )

    def _lines_for_category(self, quote: Quote, category_id: int | None, category_name: str | None) -> list[QuoteLine]:
        matched = []
        for ln in quote.lines:
            product = ln.product
            if not product:
                continue
            if category_id and product.category_id == category_id:
                matched.append(ln)
            elif category_name and product.category and product.category.name.lower() == category_name.lower():
                matched.append(ln)
        return matched

    def _create_request(
        self,
        db: Session,
        n: Negotiation,
        quote: Quote,
        user: User,
        req_type: NegotiationRequestType,
        requested,
        reason: str | None,
        line: QuoteLine | None = None,
        category_id: int | None = None,
        old_value: str | None = None,
    ) -> tuple[NegotiationRequest, dict]:
        if line and req_type == NegotiationRequestType.DISCOUNT and old_value is None:
            old_value = str(float(line.discount_percent))
        analysis = self._analyze(db, quote, line, req_type, requested)
        rec = NegotiationRequest(
            negotiation_id=n.id,
            line_id=line.id if line else None,
            category_id=category_id,
            request_type=req_type,
            old_value=old_value,
            requested_value=str(requested) if requested is not None else None,
            reason=reason,
            status=RequestStatus.PENDING,
            margin_impact=D(analysis["margin_impact"]),
            risk_impact=D(analysis["risk_impact"]),
            exception_percent=D(analysis["exception_percent"]),
            counteroffer_json=analysis.get("counteroffer"),
            acted_by=user.id,
        )
        db.add(rec)
        return rec, analysis

    def request_change(self, db: Session, quote: Quote, user: User, payload: dict) -> dict:
        from app.services.access import customer_owns_quote

        if user.role == UserRole.CUSTOMER and not customer_owns_quote(user, quote):
            raise AppError("FORBIDDEN", "You can only negotiate your own quotes.", 403)
        n = self.ensure(db, quote)
        req_type = NegotiationRequestType(payload["request_type"])
        reason = (payload.get("reason") or "").strip() or None
        if user.role == UserRole.CUSTOMER and req_type == NegotiationRequestType.DISCOUNT and not reason:
            raise AppError("VALIDATION_ERROR", "Please add a comment explaining the discount request.")

        category_discounts = [c for c in (payload.get("category_discounts") or []) if c]
        recs: list[NegotiationRequest] = []
        last_analysis: dict = {}

        if req_type == NegotiationRequestType.DISCOUNT and category_discounts:
            for item in category_discounts:
                if isinstance(item, dict):
                    cat_id = item.get("category_id")
                    cat_name = item.get("category")
                    requested = item.get("requested_percent")
                else:
                    cat_id = getattr(item, "category_id", None)
                    cat_name = getattr(item, "category", None)
                    requested = getattr(item, "requested_percent", None)
                lines = self._lines_for_category(quote, cat_id, cat_name)
                line = lines[0] if lines else None
                if line and not cat_id:
                    cat_id = line.product.category_id if line.product else None
                if not cat_name and line and line.product and line.product.category:
                    cat_name = line.product.category.name
                gross = sum(float(ln.unit_price) * ln.quantity for ln in lines) or 1
                disc_amt = sum(float(ln.discount_amount or 0) for ln in lines)
                current_pct = round(disc_amt / gross * 100, 2)
                rec, analysis = self._create_request(
                    db,
                    n,
                    quote,
                    user,
                    req_type,
                    requested,
                    reason,
                    line=line,
                    category_id=cat_id,
                    old_value=f"{cat_name or 'Category'}|{current_pct}",
                )
                max_exc = float(analysis.get("exception_percent") or 0)
                from app.services.discount import evaluate_line_discount, load_discount_rules

                rules = load_discount_rules(db)
                for ln in lines:
                    if not ln.product:
                        continue
                    ev = evaluate_line_discount(rules, quote.customer, ln.product, D(str(requested).replace("%", "")))
                    max_exc = max(max_exc, float(ev["exception_percent"]))
                rec.exception_percent = D(max_exc)
                recs.append(rec)
                last_analysis = analysis
                last_analysis["category"] = cat_name
                last_analysis["exception_percent"] = max_exc
            requested = ", ".join(f"{(r.old_value or '').split('|')[0]} {r.requested_value}%" for r in recs)
        else:
            line = db.get(QuoteLine, payload["line_id"]) if payload.get("line_id") else None
            requested = payload.get("requested_value")
            rec, last_analysis = self._create_request(
                db,
                n,
                quote,
                user,
                req_type,
                requested,
                reason,
                line=line,
                old_value=payload.get("old_value"),
            )
            recs.append(rec)

        n.last_counteroffer_json = last_analysis.get("counteroffer")
        n.status = NegotiationStatus.COUNTERED if last_analysis.get("counteroffer") else NegotiationStatus.OPEN
        mark_under_negotiation(quote)
        db.flush()
        event_bus.publish(
            EventType.CUSTOMER_NEGOTIATED,
            {
                "quote_id": quote.id,
                "actor_id": user.id,
                "description": f"Customer requested {req_type.value.lower().replace('_', ' ')}: {requested}",
                "metadata": {"reason": reason, "requests": [r.id for r in recs]},
            },
            db,
        )
        if last_analysis.get("counteroffer"):
            event_bus.publish(
                EventType.COUNTEROFFER_GENERATED,
                {
                    "quote_id": quote.id,
                    "actor_id": user.id,
                    "description": last_analysis["counteroffer"]["headline"],
                    "metadata": last_analysis["counteroffer"],
                },
                db,
            )
        self._notify_managers(
            db,
            quote,
            user,
            f"{user.name} requested a new discount. Comment: {reason or '—'}",
        )
        quote_engine.recalculate(db, quote)
        routed = False
        if user.role == UserRole.CUSTOMER:
            routed = self.maybe_route_for_approval(db, quote, user, recs)
        last_analysis["reapproval_required"] = routed
        db.flush()
        return {
            "request": recs[-1] if recs else None,
            "requests": recs,
            "analysis": last_analysis,
            "negotiation": n,
        }

    def maybe_route_for_approval(self, db: Session, quote: Quote, user: User, recs: list[NegotiationRequest]) -> bool:
        """Escalate from a customer negotiation using discount ceilings + Admin risk threshold.

        Discount over tier/category limit → Sales Manager.
        Blended risk above the configured threshold → Manager then Finance.
        Within limits and risk below threshold → no approval request.
        """
        from app.services.approval import approval_svc
        from app.services.settings import negotiation_approval_plan, risk_threshold

        exceeds, max_exc, projected_risk = self._projected_policy(db, quote, recs)
        threshold = risk_threshold(db)
        plan = negotiation_approval_plan(exceeds, projected_risk, threshold)
        if not plan["required"]:
            return False

        steps = [{"role": UserRole.SALES_MANAGER, "sequence": 1}]
        reasons = []
        if exceeds:
            reasons.append(
                f"Requested discount exceeds the customer-tier or category ceiling (excess {max_exc:.1f} pts)."
            )
        if plan["risk_high"]:
            reasons.append(f"Blended risk {projected_risk:.0f} exceeds the configured threshold {threshold:.0f}.")
            steps.append({"role": UserRole.FINANCE, "sequence": 2})
        approval_svc.submit_plan(db, quote, user, steps, reasons, risk_score=projected_risk)
        return True

    def _projected_policy(self, db: Session, quote: Quote, recs: list[NegotiationRequest]) -> tuple[bool, float, float]:
        """Evaluate every line against requested category discounts and score blended risk."""
        from app.services.discount import evaluate_line_discount, load_discount_rules
        from app.utils.money import D as moneyD

        rules = load_discount_rules(db)
        overlay_id: dict[int, Decimal] = {}
        overlay_name: dict[str, Decimal] = {}
        for r in recs:
            if r.request_type != NegotiationRequestType.DISCOUNT:
                continue
            try:
                requested = moneyD(str(r.requested_value or "").replace("%", ""))
            except Exception:
                continue
            if r.category_id:
                overlay_id[int(r.category_id)] = requested
            if r.old_value and "|" in r.old_value:
                overlay_name[r.old_value.split("|", 1)[0].lower()] = requested
        exceeds = False
        max_exc = 0.0
        snapshot = {ln.id: moneyD(ln.discount_percent) for ln in quote.lines}
        for ln in quote.lines:
            product = ln.product
            if not product:
                continue
            requested = moneyD(ln.discount_percent)
            if product.category_id and int(product.category_id) in overlay_id:
                requested = overlay_id[int(product.category_id)]
            elif product.category and product.category.name.lower() in overlay_name:
                requested = overlay_name[product.category.name.lower()]
            ev = evaluate_line_discount(rules, quote.customer, product, requested)
            exc = float(ev["exception_percent"])
            if exc > 0:
                exceeds = True
                max_exc = max(max_exc, exc)
            ln.discount_percent = requested
        intel = quote_engine.recalculate(db, quote)
        risk = float((intel.get("risk") or {}).get("score") or quote.risk_score or 0)
        for ln in quote.lines:
            ln.discount_percent = snapshot[ln.id]
        quote_engine.recalculate(db, quote)
        return exceeds, max_exc, risk

    def apply_pending_requests(self, db: Session, quote: Quote, user: User) -> bool:
        n = (
            db.query(Negotiation)
            .filter(Negotiation.quote_id == quote.id, Negotiation.status.in_([NegotiationStatus.OPEN, NegotiationStatus.COUNTERED]))
            .order_by(Negotiation.id.desc())
            .first()
        )
        if not n:
            return False
        pending = [r for r in n.requests if r.status == RequestStatus.PENDING]
        if not pending:
            return False
        applied = False
        for r in pending:
            if r.request_type != NegotiationRequestType.DISCOUNT:
                r.status = RequestStatus.ACCEPTED
                r.acted_by = user.id
                continue
            try:
                requested = D(str(r.requested_value or "").replace("%", ""))
            except Exception:
                continue
            cat_name = r.old_value.split("|", 1)[0] if r.old_value and "|" in r.old_value else None
            if not cat_name and getattr(r, "category", None):
                cat_name = r.category.name
            lines = self._lines_for_category(quote, r.category_id, cat_name)
            if not lines and r.line:
                lines = [r.line]
            for ln in lines:
                ln.discount_percent = requested
                applied = True
            r.status = RequestStatus.ACCEPTED
            r.acted_by = user.id
        if not applied and not pending:
            return False
        n.status = NegotiationStatus.ACCEPTED
        quote.negotiation_status = NegotiationStatus.ACCEPTED
        quote_engine.recalculate(db, quote)
        event_bus.publish(
            EventType.NEGOTIATION_ACCEPTED,
            {
                "quote_id": quote.id,
                "actor_id": user.id,
                "description": f"{user.name} accepted the customer's requested terms",
            },
            db,
        )
        db.flush()
        return True

    def reject_pending(self, db: Session, quote: Quote, user: User, comment: str | None) -> None:
        from app.models.enums import ApprovalStatus
        from app.models.governance import ApprovalRequest

        n = self.ensure(db, quote)
        pending = [r for r in n.requests if r.status == RequestStatus.PENDING]
        for r in pending:
            r.status = RequestStatus.REJECTED
            r.acted_by = user.id
        n.status = NegotiationStatus.REJECTED
        quote.negotiation_status = NegotiationStatus.REJECTED
        pending_appr = (
            db.query(ApprovalRequest)
            .filter(ApprovalRequest.quote_id == quote.id, ApprovalRequest.status == ApprovalStatus.PENDING)
            .all()
        )
        for req in pending_appr:
            req.status = ApprovalStatus.CANCELLED
        if quote.sent_to_customer_at and quote.status != QuoteStatus.CONFIRMED:
            quote.status = QuoteStatus.APPROVED
            quote.approval_status = ApprovalStatus.APPROVED
        event_bus.publish(
            EventType.NEGOTIATION_REJECTED,
            {
                "quote_id": quote.id,
                "actor_id": user.id,
                "description": comment or "Negotiation request rejected",
            },
            db,
        )
        if quote.sales_rep_id and quote.sales_rep_id != user.id:
            notify(
                db,
                quote.sales_rep_id,
                "NEGOTIATION_REJECTED",
                "Negotiation rejected",
                f"{quote.quote_number}: {comment or 'Customer request declined.'}",
                Severity.MEDIUM,
                "quote",
                quote.id,
            )
        db.flush()

    def return_to_rep(self, db: Session, quote: Quote, user: User, comment: str | None) -> None:
        from app.models.enums import ApprovalStatus, ApprovalStepStatus
        from app.models.governance import ApprovalRequest

        if not (comment or "").strip():
            raise AppError("VALIDATION_ERROR", "Please add a reason for the sales rep.")
        n = (
            db.query(Negotiation)
            .filter(Negotiation.quote_id == quote.id)
            .order_by(Negotiation.id.desc())
            .first()
        )
        pending_appr = (
            db.query(ApprovalRequest)
            .filter(ApprovalRequest.quote_id == quote.id, ApprovalRequest.status == ApprovalStatus.PENDING)
            .all()
        )
        for req in pending_appr:
            req.status = ApprovalStatus.CHANGES_REQUESTED
            for step in req.steps:
                if step.status == ApprovalStepStatus.PENDING:
                    step.comment = comment
                    step.approver_id = user.id
                    step.acted_at = datetime.utcnow()
        quote.status = QuoteStatus.DRAFT
        quote.approval_status = ApprovalStatus.CHANGES_REQUESTED
        event_bus.publish(
            EventType.APPROVAL_CHANGES_REQUESTED,
            {
                "quote_id": quote.id,
                "actor_id": user.id,
                "description": f"Returned to sales rep" + (f": {comment}" if comment else ""),
                "metadata": {"negotiation_id": n.id if n else None},
            },
            db,
        )
        notify(
            db,
            quote.sales_rep_id,
            "CHANGES_REQUESTED",
            "Returned for revision",
            f"{quote.quote_number}: {comment}",
            Severity.MEDIUM,
            "quote",
            quote.id,
        )
        db.flush()

    def accept_counteroffer(self, db: Session, quote: Quote, user: User, request_id: int | None = None) -> Quote:
        n = self.ensure(db, quote)
        req = None
        if request_id:
            req = db.get(NegotiationRequest, request_id)
        else:
            req = (
                db.query(NegotiationRequest)
                .filter(NegotiationRequest.negotiation_id == n.id, NegotiationRequest.status == RequestStatus.PENDING)
                .order_by(NegotiationRequest.id.desc())
                .first()
            )
        if not req or not req.counteroffer_json:
            raise AppError("NOT_FOUND", "No counteroffer to accept.")
        offer = req.counteroffer_json
        line = req.line
        if line and offer.get("discount_percent") is not None:
            line.discount_percent = D(offer["discount_percent"])
        if offer.get("add_product_id"):
            quote_engine.add_product(
                db,
                quote,
                user,
                int(offer["add_product_id"]),
                1,
                100 if offer.get("add_as_freebie") else 0,
            )
            # mark last line freebie
            if offer.get("add_as_freebie") and quote.lines:
                quote.lines[-1].is_freebie = True
                quote.lines[-1].discount_percent = D(100)
        req.status = RequestStatus.ACCEPTED
        n.status = NegotiationStatus.ACCEPTED
        quote.negotiation_status = NegotiationStatus.ACCEPTED
        quote_engine.recalculate(db, quote)
        from app.services.approval import approval_svc

        ctx = quote_engine._approval_context(quote, quote_engine._last_intel)
        reopened = approval_svc.invalidate_if_material(db, quote, ctx, user)
        event_bus.publish(
            EventType.NEGOTIATION_ACCEPTED,
            {
                "quote_id": quote.id,
                "actor_id": user.id,
                "description": "Customer accepted counteroffer"
                + ("; previous approval invalidated" if reopened else ""),
            },
            db,
        )
        db.flush()
        return quote

    def accept_quote(self, db: Session, quote: Quote, user: User) -> Quote:
        n = self.ensure(db, quote)
        n.status = NegotiationStatus.ACCEPTED
        quote.negotiation_status = NegotiationStatus.ACCEPTED
        event_bus.publish(
            EventType.NEGOTIATION_ACCEPTED,
            {"quote_id": quote.id, "actor_id": user.id, "description": "Customer accepted the quote as presented"},
            db,
        )
        db.flush()
        return quote

    def reject_request(self, db: Session, quote: Quote, user: User, request_id: int, comment: str | None) -> None:
        req = db.get(NegotiationRequest, request_id)
        if not req:
            raise AppError("NOT_FOUND", "Request not found.")
        req.status = RequestStatus.REJECTED
        event_bus.publish(
            EventType.NEGOTIATION_REJECTED,
            {
                "quote_id": quote.id,
                "actor_id": user.id,
                "description": comment or "Negotiation request rejected",
            },
            db,
        )

    def _analyze(self, db: Session, quote: Quote, line: QuoteLine | None, req_type: NegotiationRequestType, requested) -> dict:
        result = {
            "requested_discount": None,
            "allowed_discount": None,
            "exception_percent": 0,
            "margin_impact": 0,
            "risk_impact": 0,
            "counteroffer": None,
        }
        if req_type != NegotiationRequestType.DISCOUNT or line is None:
            # still produce a friendly counter for payment terms
            if req_type == NegotiationRequestType.PAYMENT_TERMS:
                try:
                    days = int(float(requested))
                except (TypeError, ValueError):
                    days = quote.payment_terms
                if days > quote.payment_terms:
                    result["counteroffer"] = {
                        "headline": f"We can extend terms to {min(days, quote.payment_terms + 15)} days",
                        "instead_of": f"{days} days",
                        "offer": f"{min(days, quote.payment_terms + 15)} days net",
                        "customer_value": 0,
                        "profit_preserved": 0,
                    }
            return result

        try:
            requested_disc = D(str(requested).replace("%", ""))
        except Exception:
            requested_disc = D(line.discount_percent)
        rules = load_discount_rules(db)
        product = line.product or db.get(Product, line.product_id)
        ev = evaluate_line_discount(rules, quote.customer, product, requested_disc)
        current = calculate_line(line.quantity, D(line.unit_price), D(line.unit_cost), D(line.discount_percent))
        proposed = calculate_line(line.quantity, D(line.unit_price), D(line.unit_cost), requested_disc)
        margin_impact = money(proposed["gross_profit"] - current["gross_profit"])
        exception = D(ev["exception_percent"])
        risk_impact = float(min(exception * D(3) + (D(8) if exception > 0 else 0), D(20)))
        result.update(
            {
                "requested_discount": float(requested_disc),
                "allowed_discount": float(ev["allowed_percent"]),
                "exception_percent": float(exception),
                "margin_impact": float(margin_impact),
                "risk_impact": risk_impact,
                "evaluation": {k: (float(v) if isinstance(v, Decimal) else v) for k, v in ev.items()},
            }
        )
        if exception > 0:
            # Offer allowed + 1–2 pts plus a free high-perceived-value service
            offered_disc = min(requested_disc, D(ev["allowed_percent"]) + D(6))
            offered_disc = max(D(ev["allowed_percent"]), offered_disc)
            if offered_disc >= requested_disc:
                offered_disc = D(ev["allowed_percent"]) + D(1)
            mid = calculate_line(line.quantity, D(line.unit_price), D(line.unit_cost), offered_disc)
            profit_preserved = money(mid["gross_profit"] - proposed["gross_profit"])
            install = db.query(Product).filter(Product.sku == "INST-01").first()
            customer_value = money(D(install.perceived_value or install.base_price) if install else D(15000))
            result["counteroffer"] = {
                "headline": f"Instead of {float(requested_disc):.0f}% discount, offer {float(offered_disc):.0f}% + free installation",
                "instead_of": f"{float(requested_disc):.0f}% discount",
                "offer": f"{float(offered_disc):.0f}% discount + Free installation",
                "discount_percent": float(offered_disc),
                "add_product_id": install.id if install else None,
                "add_as_freebie": True,
                "add_product_name": install.name if install else "Installation Service",
                "customer_value": float(customer_value),
                "profit_preserved": float(profit_preserved),
                "requested_margin_hit": float(margin_impact),
            }
        return result
