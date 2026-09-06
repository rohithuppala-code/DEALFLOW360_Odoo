from app.models.enums import ApprovalStatus, NegotiationStatus, QuoteStatus
from app.models.quote import Quote

STAGES = [
    ("quote", "Quote", "Build lines, discount, and pricing"),
    ("approve", "Approve", "Policy, margin, and risk review"),
    ("share", "Share", "Send the commercial offer"),
    ("negotiate", "Negotiate", "Customer requests and counters"),
    ("fulfill", "Fulfill", "Warehouse plan and inventory"),
    ("close", "Close", "Confirm, reserve stock, and bill"),
]


def _stage_state(index: int, current: int, lost: bool) -> str:
    if lost:
        if index < current:
            return "done"
        if index == current:
            return "blocked"
        return "todo"
    if index < current:
        return "done"
    if index == current:
        return "current"
    return "todo"


def current_stage_key(quote: Quote) -> str:
    status = quote.status
    if status in (QuoteStatus.CANCELLED, QuoteStatus.REJECTED):
        return "close"
    if status == QuoteStatus.CONFIRMED:
        return "close"
    if status == QuoteStatus.NEGOTIATING:
        return "negotiate"
    if status == QuoteStatus.PENDING_APPROVAL:
        return "approve"
    if status == QuoteStatus.APPROVED:
        if not quote.sent_to_customer_at:
            return "share"
        return "fulfill"
    return "quote"


def build_workflow(quote: Quote, intel: dict | None = None, viewer=None) -> dict:
    intel = intel or {}
    preview = intel.get("approval_preview") or {}
    reasons = [r for r in (preview.get("reasons") or []) if r]
    roles = [r for r in (preview.get("roles") or []) if r]
    required = bool(preview.get("required"))
    if quote.status == QuoteStatus.PENDING_APPROVAL:
        required = True
    if quote.approval_status not in (ApprovalStatus.NOT_REQUIRED, ApprovalStatus.APPROVED) and quote.status != QuoteStatus.DRAFT:
        required = True

    lost = quote.status in (QuoteStatus.CANCELLED, QuoteStatus.REJECTED)
    current_key = current_stage_key(quote)
    keys = [s[0] for s in STAGES]
    current_idx = keys.index(current_key)

    stages = []
    for i, (key, label, hint) in enumerate(STAGES):
        stage_hint = hint
        if key == "approve" and not required and quote.status == QuoteStatus.DRAFT:
            stage_hint = "Skipped automatically when the deal stays within policy"
        if key == "negotiate" and quote.negotiation_status in (NegotiationStatus.NONE, None) and current_idx < i:
            stage_hint = "Only if the customer requests a change"
        stages.append(
            {
                "key": key,
                "label": label,
                "hint": stage_hint,
                "state": _stage_state(i, current_idx, lost),
            }
        )

    sent = bool(quote.sent_to_customer_at)
    action = {
        "id": "none",
        "label": "No action needed",
        "reason": "This deal is already closed.",
        "tone": "info",
    }

    pending_req = next(
        (r for r in getattr(quote, "approval_requests", []) if getattr(r.status, "value", str(r.status)) == "PENDING"),
        None,
    )
    active_step = None
    if pending_req and getattr(pending_req, "steps", None):
        pending_steps = [s for s in pending_req.steps if getattr(s.status, "value", str(s.status)) == "PENDING"]
        if pending_steps:
            active_step = min(pending_steps, key=lambda s: getattr(s, "sequence", 1))

    active_step_role = getattr(getattr(active_step, "role", None), "value", str(getattr(active_step, "role", ""))) if active_step else ""
    viewer_role = getattr(getattr(viewer, "role", None), "value", str(getattr(viewer, "role", ""))) if viewer else ""

    # Robust fallback for effective role if step collection was empty or partially loaded
    effective_role = active_step_role
    if not effective_role and pending_req and getattr(pending_req, "steps", None):
        unapproved = [s for s in pending_req.steps if getattr(s.status, "value", str(s.status)) not in ("APPROVED", "SKIPPED")]
        if unapproved:
            effective_role = getattr(getattr(min(unapproved, key=lambda s: getattr(s, "sequence", 1)), "role", None), "value", "")

    if not effective_role:
        if roles:
            effective_role = roles[0]
        elif quote.status == QuoteStatus.PENDING_APPROVAL:
            effective_role = "SALES_MANAGER"

    waiting_role = (
        effective_role.replace("_", " ").title()
        if effective_role
        else "Sales Manager"
    )

    can_act = bool(viewer and (viewer_role == "ADMIN" or (effective_role and viewer_role == effective_role)))

    if quote.status == QuoteStatus.REJECTED:
        action = {
            "id": "revise",
            "label": "Revise and resubmit",
            "reason": "Approval was declined. Adjust discount or mix, then request approval again.",
            "tone": "warn",
        }
    elif quote.status == QuoteStatus.CANCELLED:
        action = {
            "id": "none",
            "label": "Cancelled",
            "reason": "This quote is no longer active.",
            "tone": "bad",
        }
    elif quote.status == QuoteStatus.CONFIRMED:
        action = {
            "id": "billing",
            "label": "Open billing",
            "reason": "Order is confirmed. Inventory is reserved and invoices are in billing.",
            "tone": "good",
        }
    elif quote.status == QuoteStatus.DRAFT:
        if required:
            action = {
                "id": "submit",
                "label": "Request approval",
                "reason": reasons[0] if reasons else "Policy requires a manager or finance review before this deal can move.",
                "tone": "warn",
            }
        else:
            action = {
                "id": "submit",
                "label": "Submit deal",
                "reason": "Within policy. Submit to auto-approve, then share with the customer.",
                "tone": "good",
            }
    elif quote.status == QuoteStatus.PENDING_APPROVAL:
        if can_act:
            action = {
                "id": "approve",
                "label": f"Review & Approve ({waiting_role})",
                "reason": f"Approval requested from {waiting_role}. Review terms and approve or reject.",
                "tone": "accent",
                "can_act": True,
                "approval_id": pending_req.id if pending_req else None,
            }
        elif viewer_role == "FINANCE" and any(
            getattr(getattr(s, "role", None), "value", str(getattr(s, "role", ""))) == "FINANCE"
            for s in getattr(pending_req, "steps", [])
        ):
            action = {
                "id": "wait",
                "label": "Waiting for Sales Manager (Step 1)",
                "reason": "High-risk deal requires Sales Manager review first, then forwards to Finance.",
                "tone": "info",
                "can_act": False,
                "approval_id": pending_req.id if pending_req else None,
            }
        else:
            action = {
                "id": "wait",
                "label": "Waiting for approval",
                "reason": f"Forwarded to {waiting_role}. You will be notified when they act.",
                "tone": "info",
                "can_act": False,
                "approval_id": pending_req.id if pending_req else None,
            }
    elif quote.status == QuoteStatus.APPROVED and not sent:
        action = {
            "id": "send",
            "label": "Send to customer",
            "reason": "Approved internally. Share the offer so the customer can accept or negotiate.",
            "tone": "good",
        }
    elif quote.status == QuoteStatus.NEGOTIATING:
        action = {
            "id": "negotiate",
            "label": "Review negotiation",
            "reason": "The customer requested a change. Review the counteroffer, then re-approve if needed.",
            "tone": "info",
        }
    elif quote.status in (QuoteStatus.APPROVED, QuoteStatus.NEGOTIATING) and sent:
        action = {
            "id": "confirm",
            "label": "Confirm order",
            "reason": "Lock inventory, create the order, and raise the invoice.",
            "tone": "accent",
        }

    return {
        "current_key": current_key,
        "lost": lost,
        "approval_required": required,
        "approval_reasons": reasons,
        "approval_roles": roles,
        "stages": stages,
        "next_action": action,
        "can_submit": quote.status == QuoteStatus.DRAFT,
        "can_send": quote.status in (QuoteStatus.APPROVED, QuoteStatus.NEGOTIATING),
        "can_confirm": quote.status in (QuoteStatus.APPROVED, QuoteStatus.NEGOTIATING)
        and quote.approval_status in (ApprovalStatus.APPROVED, ApprovalStatus.NOT_REQUIRED),
        "sent_to_customer": sent,
        "can_approve": can_act,
        "active_approval_id": pending_req.id if pending_req else None,
        "active_approver_role": active_step_role,
    }
