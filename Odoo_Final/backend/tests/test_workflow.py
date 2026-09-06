from datetime import UTC, datetime

from app.models.enums import ApprovalStatus, NegotiationStatus, QuoteStatus
from app.models.quote import Quote
from app.services.negotiation import mark_under_negotiation
from app.services.workflow import build_workflow, current_stage_key


def _quote(**kwargs) -> Quote:
    defaults = dict(
        status=QuoteStatus.DRAFT,
        approval_status=ApprovalStatus.NOT_REQUIRED,
        negotiation_status=NegotiationStatus.NONE,
        sent_to_customer_at=None,
    )
    defaults.update(kwargs)
    return Quote(**defaults)


def test_draft_with_policy_exception_asks_for_approval():
    q = _quote()
    wf = build_workflow(
        q,
        {"approval_preview": {"required": True, "reasons": ["Service discount exceeds Gold cap"], "roles": ["SALES_MANAGER"]}},
    )
    assert current_stage_key(q) == "quote"
    assert wf["next_action"]["id"] == "submit"
    assert wf["can_submit"] is True
    assert wf["stages"][0]["state"] == "current"


def test_pending_approval_waits():
    q = _quote(status=QuoteStatus.PENDING_APPROVAL, approval_status=ApprovalStatus.PENDING)
    wf = build_workflow(q, {"approval_preview": {"required": True, "roles": ["FINANCE"]}})
    assert wf["current_key"] == "approve"
    assert wf["next_action"]["id"] == "wait"


def test_approved_unsent_sends_to_customer():
    q = _quote(status=QuoteStatus.APPROVED, approval_status=ApprovalStatus.APPROVED)
    wf = build_workflow(q)
    assert wf["current_key"] == "share"
    assert wf["next_action"]["id"] == "send"
    assert wf["can_send"] is True


def test_approved_sent_confirms():
    q = _quote(
        status=QuoteStatus.APPROVED,
        approval_status=ApprovalStatus.APPROVED,
        sent_to_customer_at=datetime.now(UTC),
    )
    wf = build_workflow(q)
    assert wf["current_key"] == "fulfill"
    assert wf["next_action"]["id"] == "confirm"


def test_customer_request_marks_under_negotiation():
    q = _quote(status=QuoteStatus.APPROVED, approval_status=ApprovalStatus.APPROVED)
    mark_under_negotiation(q)
    assert q.status == QuoteStatus.NEGOTIATING
    assert q.negotiation_status == NegotiationStatus.OPEN


def test_confirmed_points_to_billing():
    q = _quote(status=QuoteStatus.CONFIRMED, approval_status=ApprovalStatus.APPROVED)
    wf = build_workflow(q)
    assert wf["current_key"] == "close"
    assert wf["next_action"]["id"] == "billing"
    assert all(s["state"] == "done" or s["key"] == "close" for s in wf["stages"])


def test_manager_sees_approve_action_when_pending():
    from types import SimpleNamespace
    from app.models.enums import ApprovalStepStatus, UserRole
    from app.models.governance import ApprovalRequest, ApprovalStep

    manager = SimpleNamespace(id=2, role=UserRole.SALES_MANAGER)
    rep = SimpleNamespace(id=1, role=UserRole.SALES_REP)

    req = ApprovalRequest(id=10, status=ApprovalStatus.PENDING)
    step = ApprovalStep(id=1, role=UserRole.SALES_MANAGER, status=ApprovalStepStatus.PENDING, sequence=1)
    req.steps = [step]
    q = _quote(status=QuoteStatus.PENDING_APPROVAL, approval_status=ApprovalStatus.PENDING)
    q.approval_requests = [req]

    # Manager viewer
    wf_mgr = build_workflow(q, viewer=manager)
    assert wf_mgr["can_approve"] is True
    assert wf_mgr["next_action"]["id"] == "approve"
    assert "Sales Manager" in wf_mgr["next_action"]["label"]

    # Rep viewer
    wf_rep = build_workflow(q, viewer=rep)
    assert wf_rep["can_approve"] is False
    assert wf_rep["next_action"]["id"] == "wait"
    assert "Forwarded to Sales Manager" in wf_rep["next_action"]["reason"]


def test_multi_step_high_risk_approval_flow():
    from types import SimpleNamespace
    from app.models.enums import ApprovalStepStatus, UserRole
    from app.models.governance import ApprovalRequest, ApprovalStep

    manager = SimpleNamespace(id=2, role=UserRole.SALES_MANAGER)
    finance = SimpleNamespace(id=3, role=UserRole.FINANCE)

    req = ApprovalRequest(id=10, status=ApprovalStatus.PENDING)
    step1 = ApprovalStep(id=1, role=UserRole.SALES_MANAGER, status=ApprovalStepStatus.PENDING, sequence=1)
    step2 = ApprovalStep(id=2, role=UserRole.FINANCE, status=ApprovalStepStatus.WAITING, sequence=2)
    req.steps = [step1, step2]
    q = _quote(status=QuoteStatus.PENDING_APPROVAL, approval_status=ApprovalStatus.PENDING)
    q.approval_requests = [req]

    # While Step 1 is pending: Manager can approve, Finance waits for Manager
    wf_mgr = build_workflow(q, viewer=manager)
    assert wf_mgr["can_approve"] is True
    assert wf_mgr["next_action"]["id"] == "approve"

    wf_fin = build_workflow(q, viewer=finance)
    assert wf_fin["can_approve"] is False
    assert wf_fin["next_action"]["id"] == "wait"
    assert "Waiting for Sales Manager (Step 1)" in wf_fin["next_action"]["label"]

    # Now step 1 is approved, step 2 is pending
    step1.status = ApprovalStepStatus.APPROVED
    step2.status = ApprovalStepStatus.PENDING

    wf_mgr_after = build_workflow(q, viewer=manager)
    assert wf_mgr_after["can_approve"] is False

    wf_fin_after = build_workflow(q, viewer=finance)
    assert wf_fin_after["can_approve"] is True
    assert wf_fin_after["next_action"]["id"] == "approve"
    assert "Finance" in wf_fin_after["next_action"]["label"]

