from datetime import datetime

from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.events.bus import audit, event_bus, notify
from app.models.enums import (
    ApprovalStatus,
    ApprovalStepStatus,
    ConditionType,
    EventType,
    QuoteStatus,
    Severity,
    UserRole,
)
from app.models.governance import ApprovalChain, ApprovalRequest, ApprovalRule, ApprovalStep
from app.models.quote import Quote
from app.models.user import User
from app.utils.money import D


class ApprovalRoutingService:
    def required_steps(self, db: Session, quote: Quote, context: dict) -> list[dict]:
        chain = db.query(ApprovalChain).filter(ApprovalChain.is_active.is_(True)).first()
        if not chain:
            return []
        needed: dict[tuple[int, UserRole], dict] = {}
        reasons: list[str] = []
        for rule in chain.rules:
            if self._matches(db, rule, quote, context):
                key = (rule.sequence, rule.required_role)
                needed[key] = {
                    "role": rule.required_role,
                    "sequence": rule.sequence,
                    "condition": rule.condition_type,
                    "value": rule.condition_value,
                }
                reasons.append(self._reason(db, rule, quote, context))
        steps = sorted(needed.values(), key=lambda s: (s["sequence"], s["role"].value))
        return steps, reasons  # type: ignore[return-value]

    def evaluate(self, db: Session, quote: Quote, context: dict) -> dict:
        result = self.required_steps(db, quote, context)
        steps, reasons = result if isinstance(result, tuple) else (result, [])
        return {
            "required": bool(steps),
            "steps": [
                {"role": s["role"].value if hasattr(s["role"], "value") else s["role"], "sequence": s["sequence"]}
                for s in steps
            ],
            "reasons": reasons,
            "roles": list({(s["role"].value if hasattr(s["role"], "value") else s["role"]) for s in steps}),
        }

    def submit(self, db: Session, quote: Quote, user: User, context: dict) -> ApprovalRequest:
        evaluation = self.evaluate(db, quote, context)
        if not evaluation["required"]:
            quote.approval_status = ApprovalStatus.NOT_REQUIRED
            quote.status = QuoteStatus.APPROVED
            return None  # type: ignore[return-value]

        # cancel previous pending
        pending = (
            db.query(ApprovalRequest)
            .filter(ApprovalRequest.quote_id == quote.id, ApprovalRequest.status == ApprovalStatus.PENDING)
            .all()
        )
        for req in pending:
            req.status = ApprovalStatus.CANCELLED

        is_reapproval = quote.approval_status == ApprovalStatus.APPROVED
        req = ApprovalRequest(
            quote_id=quote.id,
            requested_by=user.id,
            status=ApprovalStatus.PENDING,
            risk_score=quote.risk_score,
            reason="; ".join(evaluation["reasons"]) or "Policy requires approval.",
            is_reapproval=is_reapproval,
        )
        db.add(req)
        db.flush()
        steps, _ = self.required_steps(db, quote, context)
        # activate first sequence
        min_seq = min(s["sequence"] for s in steps)
        for s in steps:
            status = ApprovalStepStatus.PENDING if s["sequence"] == min_seq else ApprovalStepStatus.WAITING
            db.add(
                ApprovalStep(
                    approval_request_id=req.id,
                    role=s["role"],
                    sequence=s["sequence"],
                    status=status,
                )
            )
        quote.approval_status = ApprovalStatus.PENDING
        quote.status = QuoteStatus.PENDING_APPROVAL
        db.flush()
        event_bus.publish(
            EventType.APPROVAL_REQUESTED,
            {
                "quote_id": quote.id,
                "actor_id": user.id,
                "description": f"Approval requested: {req.reason}",
                "metadata": evaluation,
            },
            db,
        )
        first_seq = min(s["sequence"] for s in steps)
        self._notify_approvers(db, quote, [s for s in steps if s["sequence"] == first_seq])
        audit(db, user.id, "APPROVAL_SUBMIT", "quote", quote.id, new_value={"reasons": evaluation["reasons"]})
        return req

    def submit_plan(
        self,
        db: Session,
        quote: Quote,
        user: User,
        steps: list[dict],
        reasons: list[str],
        risk_score=None,
    ) -> ApprovalRequest | None:
        """Create one approval request with an explicit manager/finance chain. Cancels any pending request first."""
        if not steps:
            return None
        pending = (
            db.query(ApprovalRequest)
            .filter(ApprovalRequest.quote_id == quote.id, ApprovalRequest.status == ApprovalStatus.PENDING)
            .all()
        )
        for req in pending:
            req.status = ApprovalStatus.CANCELLED
        is_reapproval = quote.approval_status == ApprovalStatus.APPROVED
        req = ApprovalRequest(
            quote_id=quote.id,
            requested_by=user.id,
            status=ApprovalStatus.PENDING,
            risk_score=D(risk_score if risk_score is not None else quote.risk_score),
            reason="; ".join([r for r in reasons if r]) or "Policy requires approval.",
            is_reapproval=is_reapproval,
        )
        db.add(req)
        db.flush()
        min_seq = min(int(s["sequence"]) for s in steps)
        seen: set[tuple] = set()
        for s in steps:
            role = s["role"]
            if isinstance(role, str):
                role = UserRole(role)
            key = (int(s["sequence"]), role)
            if key in seen:
                continue
            seen.add(key)
            db.add(
                ApprovalStep(
                    approval_request_id=req.id,
                    role=role,
                    sequence=int(s["sequence"]),
                    status=ApprovalStepStatus.PENDING if int(s["sequence"]) == min_seq else ApprovalStepStatus.WAITING,
                )
            )
        quote.approval_status = ApprovalStatus.PENDING
        quote.status = QuoteStatus.PENDING_APPROVAL
        db.flush()
        event_bus.publish(
            EventType.APPROVAL_REQUESTED,
            {
                "quote_id": quote.id,
                "actor_id": user.id,
                "description": f"Approval requested: {req.reason}",
                "metadata": {"reasons": reasons, "risk": float(req.risk_score or 0)},
            },
            db,
        )
        self._notify_approvers(db, quote, [s for s in steps if int(s["sequence"]) == min_seq])
        audit(db, user.id, "APPROVAL_SUBMIT", "quote", quote.id, new_value={"reasons": reasons})
        return req

    def act(
        self,
        db: Session,
        request: ApprovalRequest,
        user: User,
        action: str,
        comment: str | None,
    ) -> ApprovalRequest:
        if request.status != ApprovalStatus.PENDING:
            raise AppError("INVALID_APPROVAL", "This approval is no longer pending.")
        if user.role not in (UserRole.SALES_MANAGER, UserRole.FINANCE, UserRole.ADMIN):
            raise AppError("FORBIDDEN", "You cannot act on approvals.", 403)
        if action in ("reject", "request_changes") and not (comment or "").strip():
            raise AppError("VALIDATION_ERROR", "Please add a reason for the sales rep.")
        open_steps = [s for s in request.steps if getattr(s.status, "value", str(s.status)) == "PENDING"]
        if not open_steps and request.steps:
            unapproved = [s for s in request.steps if getattr(s.status, "value", str(s.status)) != "APPROVED"]
            if unapproved:
                min_seq = min(s.sequence for s in unapproved)
                for s in request.steps:
                    if s.sequence == min_seq and getattr(s.status, "value", str(s.status)) != "APPROVED":
                        s.status = ApprovalStepStatus.PENDING
                open_steps = [s for s in request.steps if getattr(s.status, "value", str(s.status)) == "PENDING"]

        user_role_str = getattr(user.role, "value", str(user.role))
        mine = [
            s
            for s in open_steps
            if s.role == user.role
            or getattr(s.role, "value", str(s.role)) == user_role_str
            or user_role_str == "ADMIN"
        ]
        if not mine:
            if user_role_str in ("ADMIN", "SALES_MANAGER") and open_steps:
                mine = [open_steps[0]]
            else:
                raise AppError("FORBIDDEN", "You are not the current approver for this request.", 403)

        step = mine[0]
        step.approver_id = user.id
        step.comment = (comment or "").strip() or None
        step.acted_at = datetime.utcnow()
        quote = request.quote

        if action == "reject":
            step.status = ApprovalStepStatus.REJECTED
            request.status = ApprovalStatus.REJECTED
            quote.approval_status = ApprovalStatus.REJECTED
            quote.status = QuoteStatus.REJECTED
            event_bus.publish(
                EventType.APPROVAL_REJECTED,
                {
                    "quote_id": quote.id,
                    "actor_id": user.id,
                    "description": f"Approval rejected by {user.name}" + (f": {comment}" if comment else ""),
                },
                db,
            )
            notify(
                db,
                quote.sales_rep_id,
                "APPROVAL_REJECTED",
                "Quote rejected",
                f"{quote.quote_number} was rejected by {user.name}" + (f": {comment}" if comment else "."),
                Severity.HIGH,
                "quote",
                quote.id,
            )
            self._notify_quote_customer(
                db,
                quote,
                "QUOTE_REJECTED",
                "Offer update",
                f"{quote.quote_number} was not approved internally.",
            )
        elif action == "request_changes":
            step.status = ApprovalStepStatus.REJECTED
            request.status = ApprovalStatus.CHANGES_REQUESTED
            quote.approval_status = ApprovalStatus.CHANGES_REQUESTED
            quote.status = QuoteStatus.DRAFT
            event_bus.publish(
                EventType.APPROVAL_CHANGES_REQUESTED,
                {
                    "quote_id": quote.id,
                    "actor_id": user.id,
                    "description": f"Changes requested by {user.name}" + (f": {comment}" if comment else ""),
                },
                db,
            )
            notify(
                db,
                quote.sales_rep_id,
                "CHANGES_REQUESTED",
                "Changes requested",
                f"{quote.quote_number}: {comment or 'Please revise the deal.'}",
                Severity.MEDIUM,
                "quote",
                quote.id,
            )
        else:
            step.status = ApprovalStepStatus.APPROVED
            if user.role in (UserRole.SALES_MANAGER, UserRole.ADMIN):
                from app.services.negotiation import NegotiationIntelligenceService
                from app.services.quote import quote_engine

                NegotiationIntelligenceService().apply_pending_requests(db, quote, user)
                quote_engine.recalculate(db, quote)
                self._append_missing_steps(db, request, quote)
            remaining = [
                s
                for s in request.steps
                if s.status in (ApprovalStepStatus.WAITING, ApprovalStepStatus.PENDING) and s.id != step.id
            ]
            next_seq = min((s.sequence for s in remaining if s.status == ApprovalStepStatus.WAITING), default=None)
            if next_seq is not None:
                nxt = [s for s in remaining if s.sequence == next_seq]
                for s in nxt:
                    s.status = ApprovalStepStatus.PENDING
                self._notify_approvers(db, quote, [{"role": s.role} for s in nxt])
            else:
                still = [s for s in request.steps if s.status not in (ApprovalStepStatus.APPROVED, ApprovalStepStatus.SKIPPED)]
                if not still:
                    request.status = ApprovalStatus.APPROVED
                    quote.approval_status = ApprovalStatus.APPROVED
                    if quote.status not in (QuoteStatus.CONFIRMED, QuoteStatus.CANCELLED):
                        quote.status = QuoteStatus.APPROVED
                    if not quote.sent_to_customer_at:
                        quote.sent_to_customer_at = datetime.utcnow()
                    event = EventType.QUOTE_REAPPROVED if request.is_reapproval else EventType.APPROVAL_APPROVED
                    event_bus.publish(
                        event,
                        {
                            "quote_id": quote.id,
                            "actor_id": user.id,
                            "description": f"{'Re-approved' if request.is_reapproval else 'Approved'} by {user.name}"
                            + (f": {comment}" if comment else ""),
                        },
                        db,
                    )
                    notify(
                        db,
                        quote.sales_rep_id,
                        "APPROVAL_APPROVED",
                        "Quote approved",
                        f"{quote.quote_number} is approved and ready to send.",
                        Severity.INFO,
                        "quote",
                        quote.id,
                    )
                    self._notify_quote_customer(
                        db,
                        quote,
                        "QUOTE_APPROVED",
                        "Offer update",
                        f"{quote.quote_number} is ready for you to review.",
                    )
            event_bus.publish(
                EventType.APPROVAL_APPROVED,
                {
                    "quote_id": quote.id,
                    "actor_id": user.id,
                    "description": f"Step approved by {user.name} ({step.role.value})",
                },
                db,
            )

        audit(db, user.id, f"APPROVAL_{action.upper()}", "approval_request", request.id, new_value={"comment": comment})
        db.flush()
        return request

    def invalidate_if_material(self, db: Session, quote: Quote, context: dict, actor: User) -> bool:
        """If previously approved and still requires approval after a material change, reopen."""
        if quote.status == QuoteStatus.CONFIRMED:
            return False
        evaluation = self.evaluate(db, quote, context)
        was_approved = quote.approval_status == ApprovalStatus.APPROVED
        if was_approved and evaluation["required"]:
            quote.approval_status = ApprovalStatus.PENDING
            self.submit(db, quote, actor, context)
            event_bus.publish(
                EventType.QUOTE_UPDATED,
                {
                    "quote_id": quote.id,
                    "actor_id": actor.id,
                    "description": "Previous approval invalidated — material change requires re-approval",
                },
                db,
            )
            return True
        if not evaluation["required"] and quote.approval_status != ApprovalStatus.PENDING:
            quote.approval_status = ApprovalStatus.NOT_REQUIRED
        return False

    def _matches(self, db: Session, rule: ApprovalRule, quote: Quote, context: dict) -> bool:
        value = D(rule.condition_value) if rule.condition_type != ConditionType.DISCOUNT_EXCEEDS_TIER else None
        if rule.condition_type == ConditionType.DISCOUNT_EXCEEDS_TIER:
            return bool(context.get("has_discount_exception"))
        if rule.condition_type == ConditionType.MARGIN_BELOW:
            return D(quote.gross_margin_percent) < D(rule.condition_value)
        if rule.condition_type == ConditionType.RISK_ABOVE:
            from app.services.settings import risk_threshold

            threshold = risk_threshold(db)
            return D(quote.risk_score) > D(threshold)
        if rule.condition_type == ConditionType.DEAL_VALUE_ABOVE:
            return D(quote.total) > D(rule.condition_value)
        if rule.condition_type == ConditionType.PAYMENT_TERMS_ABOVE:
            return D(quote.payment_terms) > D(rule.condition_value)
        if rule.condition_type == ConditionType.CATEGORY_DISCOUNT_ABOVE:
            return D(context.get("max_exception") or 0) > D(rule.condition_value)
        return False

    def _reason(self, db: Session, rule: ApprovalRule, quote: Quote, context: dict) -> str:
        if rule.condition_type == ConditionType.DISCOUNT_EXCEEDS_TIER:
            return "Discount exceeds customer-tier policy."
        if rule.condition_type == ConditionType.MARGIN_BELOW:
            return f"Margin {float(quote.gross_margin_percent):.1f}% is below {rule.condition_value}%."
        if rule.condition_type == ConditionType.RISK_ABOVE:
            from app.services.settings import risk_threshold

            threshold = risk_threshold(db)
            return f"Risk score {float(quote.risk_score):.0f} exceeds the configured threshold {threshold:.0f}."
        if rule.condition_type == ConditionType.DEAL_VALUE_ABOVE:
            return f"Deal value exceeds ₹{D(rule.condition_value):,.0f}."
        if rule.condition_type == ConditionType.PAYMENT_TERMS_ABOVE:
            return f"Payment terms {quote.payment_terms} days exceed {rule.condition_value}."
        return f"{rule.condition_type.value} triggered"

    def _append_missing_steps(self, db: Session, request: ApprovalRequest, quote: Quote) -> None:
        from app.services.quote import quote_engine
        from app.services.settings import risk_threshold

        ctx = quote_engine._approval_context(quote, getattr(quote_engine, "_last_intel", None))
        evaluation = self.evaluate(db, quote, ctx)
        existing = {s.role for s in request.steps}
        seq = max((s.sequence for s in request.steps), default=1)
        added = False
        threshold = risk_threshold(db)
        for spec in evaluation.get("steps") or []:
            role = spec["role"]
            if isinstance(role, str):
                role = UserRole(role)
            if role in existing:
                continue
            if role == UserRole.FINANCE and float(quote.risk_score or 0) <= threshold:
                continue
            seq += 1
            db.add(
                ApprovalStep(
                    approval_request_id=request.id,
                    role=role,
                    sequence=seq,
                    status=ApprovalStepStatus.WAITING,
                )
            )
            existing.add(role)
            added = True
        if added:
            db.flush()
            db.refresh(request)

    def _notify_quote_customer(self, db: Session, quote: Quote, ntype: str, title: str, message: str) -> None:
        if not quote.sent_to_customer_at or not quote.customer:
            return
        from app.services.access import portal_users_for_customer

        for pu in portal_users_for_customer(db, quote.customer):
            notify(db, pu.id, ntype, title, message, Severity.INFO, "quote", quote.id)

    def _notify_approvers(self, db: Session, quote: Quote, steps: list[dict]) -> None:
        roles = {s["role"] for s in steps}
        if not roles:
            return
        users = db.query(User).filter(User.role.in_(list(roles)), User.is_active.is_(True)).all()
        for u in users:
            notify(
                db,
                u.id,
                "APPROVAL_NEEDED",
                f"{quote.quote_number} needs approval",
                f"{quote.customer.name if quote.customer else 'Customer'} · ₹{float(quote.total):,.0f} · Risk {float(quote.risk_score):.0f}",
                Severity.HIGH,
                "quote",
                quote.id,
            )


approval_svc = ApprovalRoutingService()
