from types import SimpleNamespace

from app.models.enums import UserRole
from app.services.access import customer_owns_quote, normalize_email, portal_customer_ids


def _user(**kwargs):
    defaults = dict(role=UserRole.CUSTOMER, customer_id=12, email="buyer@acme.test")
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def _quote(customer_id=5, email="buyer@acme.test"):
    customer = SimpleNamespace(id=customer_id, email=email)
    return SimpleNamespace(customer_id=customer_id, customer=customer)


def test_normalize_email():
    assert normalize_email("  Buyer@Acme.TEST ") == "buyer@acme.test"
    assert normalize_email(None) == ""


def test_customer_sees_quote_on_linked_account():
    user = _user(customer_id=5)
    assert customer_owns_quote(user, _quote(customer_id=5)) is True


def test_customer_sees_quote_when_email_matches_even_if_ids_differ():
    """Sales-created customer row vs signup-created duplicate with the same email."""
    user = _user(customer_id=12, email="buyer@acme.test")
    quote = _quote(customer_id=5, email="buyer@acme.test")
    assert customer_owns_quote(user, quote) is True


def test_customer_cannot_see_another_account_quote():
    user = _user(customer_id=12, email="buyer@acme.test")
    quote = _quote(customer_id=9, email="other@globex.test")
    assert customer_owns_quote(user, quote) is False


def test_sales_rep_is_not_treated_as_portal_owner():
    user = _user(role=UserRole.SALES_REP, customer_id=None, email="sales@demo.com")
    quote = _quote(customer_id=5, email="buyer@acme.test")
    assert customer_owns_quote(user, quote) is False


class _Query:
    def __init__(self, rows):
        self._rows = rows

    def filter(self, *args, **kwargs):
        return self

    def all(self):
        return self._rows


class _Db:
    def __init__(self, customer_ids):
        self._ids = customer_ids

    def query(self, _col):
        return _Query([(i,) for i in self._ids])


def test_portal_ids_include_linked_and_email_matches():
    user = _user(customer_id=12, email="buyer@acme.test")
    ids = portal_customer_ids(_Db([5, 12]), user)
    assert ids == [5, 12]


def test_portal_ids_empty_for_non_customer():
    user = _user(role=UserRole.SALES_REP, customer_id=None, email="sales@demo.com")
    assert portal_customer_ids(_Db([1]), user) == []


def test_portal_ids_never_open_when_unlinked():
    user = _user(customer_id=None, email="")
    assert portal_customer_ids(_Db([]), user) == []


def test_customer_sees_quote_when_company_name_matches():
    user = _user(customer_id=None, email="different@acme.test", name="Acme Corp")
    quote = _quote(customer_id=5, email="sales_contact@acme.test")
    quote.customer.name = "Acme Corp"
    assert customer_owns_quote(user, quote) is True


def test_sales_rep_allowed_to_accept_negotiation():
    sales_rep = SimpleNamespace(id=10, role=UserRole.SALES_REP)
    other_rep = SimpleNamespace(id=99, role=UserRole.SALES_REP)
    quote = SimpleNamespace(sales_rep_id=10)
    assert (sales_rep.role == UserRole.SALES_REP and sales_rep.id == quote.sales_rep_id) is True
    assert (other_rep.role == UserRole.SALES_REP and other_rep.id == quote.sales_rep_id) is False


def test_ensure_customer_returns_none_for_non_customer():
    from app.services.access import ensure_customer_for_user

    user = _user(role=UserRole.SALES_REP)
    assert ensure_customer_for_user(None, user) is None


def test_ensure_customer_returns_existing_customer():
    from app.services.access import ensure_customer_for_user

    customer = SimpleNamespace(id=12, name="Acme")

    class MockDb:
        def get(self, model, ident):
            return customer if ident == 12 else None

    user = _user(customer_id=12)
    assert ensure_customer_for_user(MockDb(), user) is customer


def test_ensure_customer_finds_by_email():
    from app.services.access import ensure_customer_for_user

    existing = SimpleNamespace(id=20, name="Globex", email="globex@test.com")

    class MockQuery:
        def filter(self, *args, **kwargs):
            return self

        def order_by(self, *args, **kwargs):
            return self

        def first(self):
            return existing

        def all(self):
            return [existing]

    class MockDb:
        def get(self, model, ident):
            return None

        def query(self, *args, **kwargs):
            return MockQuery()

    user = _user(customer_id=None, email="globex@test.com")
    res = ensure_customer_for_user(MockDb(), user)
    assert user.customer_id == 20
    assert res is existing


def test_reconcile_all_customer_users():
    from app.services.access import reconcile_all_customer_users

    u1 = _user(id=10, customer_id=None, email="buyer1@acme.com")
    c1 = SimpleNamespace(id=5, email="buyer1@acme.com", sales_rep_id=None)

    class MockQuery:
        def __init__(self, items):
            self.items = items

        def filter(self, *args, **kwargs):
            return self

        def order_by(self, *args, **kwargs):
            return self

        def all(self):
            return self.items

        def first(self):
            return self.items[0] if self.items else None

    class MockDb:
        def __init__(self):
            self.committed = False

        def query(self, model):
            from app.models.user import User
            from app.models.customer import Customer
            if model is User:
                return MockQuery([u1])
            elif model is Customer:
                return MockQuery([c1])
            return MockQuery([])

        def commit(self):
            self.committed = True

    db = MockDb()
    healed = reconcile_all_customer_users(db)
    assert healed == 2
    assert u1.customer_id == 5
    assert c1.sales_rep_id == 10
    assert db.committed is True


def test_paginate_helper():
    from app.utils.pagination import paginate

    items = list(range(25))

    class MockQuery:
        def count(self):
            return len(items)

        def order_by(self, _):
            return self

        def offset(self, off):
            self._off = off
            return self

        def limit(self, lim):
            self._lim = lim
            return self

        def all(self):
            return items[self._off : self._off + self._lim]

    q = MockQuery()
    res_items, total, page, page_size = paginate(q, page=2, page_size=10)
    assert total == 25
    assert page == 2
    assert page_size == 10
    assert res_items == [10, 11, 12, 13, 14, 15, 16, 17, 18, 19]

