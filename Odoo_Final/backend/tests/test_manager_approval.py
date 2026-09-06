from types import SimpleNamespace

from app.models.enums import ApprovalStepStatus, UserRole
from app.services.discount import evaluate_line_discount, matching_rule


def test_evaluate_line_reports_allowed_requested_excess():
    tier = SimpleNamespace(id=1, name="Gold", default_discount_limit=12)
    customer = SimpleNamespace(customer_tier_id=1, tier=tier)
    product = SimpleNamespace(id=9, name="Laptop Pro", category_id=1, category=SimpleNamespace(name="Hardware"))
    rule = SimpleNamespace(
        id=3,
        name="Gold Hardware ≤ 12%",
        customer_tier_id=1,
        product_id=None,
        category_id=1,
        max_discount_percent=12,
        requires_approval=True,
        severity="HIGH",
    )
    ev = evaluate_line_discount([rule], customer, product, 18)
    assert float(ev["allowed_percent"]) == 12
    assert float(ev["requested_percent"]) == 18
    assert float(ev["exception_percent"]) == 6
    assert ev["requires_approval"] is True


def test_matching_rule_prefers_category_over_tier():
    customer = SimpleNamespace(customer_tier_id=2)
    product = SimpleNamespace(id=1, category_id=4)
    tier_rule = SimpleNamespace(id=1, customer_tier_id=2, product_id=None, category_id=None, max_discount_percent=10)
    cat_rule = SimpleNamespace(id=2, customer_tier_id=2, product_id=None, category_id=4, max_discount_percent=8)
    hit = matching_rule([tier_rule, cat_rule], customer, product)
    assert hit is cat_rule


def test_negotiation_manager_only_when_discount_exceeds_and_risk_below_threshold():
    from app.services.settings import negotiation_approval_plan

    plan = negotiation_approval_plan(True, 40, 70)
    assert plan["required"] is True
    assert plan["roles"] == ["SALES_MANAGER"]
    assert plan["risk_high"] is False


def test_negotiation_manager_then_finance_when_risk_above_threshold():
    from app.services.settings import negotiation_approval_plan

    plan = negotiation_approval_plan(True, 80, 70)
    assert plan["roles"] == ["SALES_MANAGER", "FINANCE"]
    plan2 = negotiation_approval_plan(False, 80, 70)
    assert plan2["roles"] == ["SALES_MANAGER", "FINANCE"]


def test_negotiation_no_escalation_within_policy_and_risk():
    from app.services.settings import negotiation_approval_plan

    plan = negotiation_approval_plan(False, 20, 70)
    assert plan["required"] is False
    assert plan["roles"] == []


def test_shipping_setting_overrides_default():
    from app.services.settings import shipping_base

    class _Q:
        def filter(self, *a, **k):
            return self

        def first(self):
            return SimpleNamespace(value_json={"Ahmedabad|Mumbai": 999})

    class _Db:
        def query(self, *a, **k):
            return _Q()

    assert shipping_base(_Db(), "Ahmedabad", "Mumbai") == 999.0
    assert shipping_base(None, "Ahmedabad", "Mumbai") == 250.0


def test_manager_pending_step_is_actionable_not_waiting():
    pending = SimpleNamespace(role=UserRole.SALES_MANAGER, status=ApprovalStepStatus.PENDING)
    waiting = SimpleNamespace(role=UserRole.FINANCE, status=ApprovalStepStatus.WAITING)
    steps = [pending, waiting]
    manager_sees = any(s.role == UserRole.SALES_MANAGER and s.status == ApprovalStepStatus.PENDING for s in steps)
    finance_sees = any(s.role == UserRole.FINANCE and s.status == ApprovalStepStatus.PENDING for s in steps)
    assert manager_sees is True
    assert finance_sees is False


def test_can_act_evaluates_correct_approver_in_chain():
    from app.api.approvals import _can_act
    from app.models.enums import ApprovalStatus

    manager = SimpleNamespace(id=2, role=UserRole.SALES_MANAGER)
    finance = SimpleNamespace(id=3, role=UserRole.FINANCE)
    rep = SimpleNamespace(id=1, role=UserRole.SALES_REP)
    admin = SimpleNamespace(id=99, role=UserRole.ADMIN)

    step1 = SimpleNamespace(id=1, role=UserRole.SALES_MANAGER, status=ApprovalStepStatus.PENDING, sequence=1)
    step2 = SimpleNamespace(id=2, role=UserRole.FINANCE, status=ApprovalStepStatus.WAITING, sequence=2)
    req = SimpleNamespace(id=10, status=ApprovalStatus.PENDING, steps=[step1, step2])

    # Step 1 pending: Manager and Admin can act; Finance and Rep cannot
    assert _can_act(manager, req) is True
    assert _can_act(admin, req) is True
    assert _can_act(finance, req) is False
    assert _can_act(rep, req) is False

    # After step 1 is approved and step 2 is pending: Finance and Admin can act; Manager cannot
    step1.status = ApprovalStepStatus.APPROVED
    step2.status = ApprovalStepStatus.PENDING

    assert _can_act(manager, req) is False
    assert _can_act(finance, req) is True
    assert _can_act(admin, req) is True
    assert _can_act(rep, req) is False


def test_approval_svc_act_multistep_progression(monkeypatch):
    from app.services.approval import ApprovalRoutingService
    from app.models.enums import ApprovalStatus, QuoteStatus

    monkeypatch.setattr("app.services.quote.quote_engine.recalculate", lambda *a, **k: {})
    monkeypatch.setattr("app.services.negotiation.NegotiationIntelligenceService.apply_pending_requests", lambda *a, **k: False)

    svc = ApprovalRoutingService()
    manager = SimpleNamespace(id=2, name="Manager", role=UserRole.SALES_MANAGER)
    finance = SimpleNamespace(id=3, name="Finance", role=UserRole.FINANCE)
    quote = SimpleNamespace(
        id=99,
        quote_number="Q-99",
        status=QuoteStatus.PENDING_APPROVAL,
        approval_status=ApprovalStatus.PENDING,
        sales_rep_id=1,
        customer=None,
        sent_to_customer_at=None,
    )
    step1 = SimpleNamespace(id=1, role=UserRole.SALES_MANAGER, sequence=1, status=ApprovalStepStatus.PENDING, approver_id=None, comment=None, acted_at=None)
    step2 = SimpleNamespace(id=2, role=UserRole.FINANCE, sequence=2, status=ApprovalStepStatus.WAITING, approver_id=None, comment=None, acted_at=None)
    req = SimpleNamespace(id=10, status=ApprovalStatus.PENDING, is_reapproval=False, quote=quote, steps=[step1, step2])

    class MockDb:
        def commit(self): pass
        def flush(self): pass
        def add(self, *a): pass

    db = MockDb()
    svc._append_missing_steps = lambda *a, **k: None
    svc._notify_approvers = lambda *a, **k: None

    # Manager approves step 1 -> step 1 APPROVED, step 2 becomes PENDING, quote stays PENDING_APPROVAL
    svc.act(db, req, manager, "approve", "Approved by manager")
    assert step1.status == ApprovalStepStatus.APPROVED
    assert step1.approver_id == manager.id
    assert step2.status == ApprovalStepStatus.PENDING
    assert req.status == ApprovalStatus.PENDING
    assert quote.status == QuoteStatus.PENDING_APPROVAL

    # Finance approves step 2 -> step 2 APPROVED, request APPROVED, quote APPROVED
    svc.act(db, req, finance, "approve", "Approved by finance")
    assert step2.status == ApprovalStepStatus.APPROVED
    assert step2.approver_id == finance.id
    assert req.status == ApprovalStatus.APPROVED
    assert quote.status == QuoteStatus.APPROVED
    assert quote.approval_status == ApprovalStatus.APPROVED

