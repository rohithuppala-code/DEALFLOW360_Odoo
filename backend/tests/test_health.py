"""Smoke tests for Phase 1.

These assert the API contract and the ORM schema. The database assertions
adapt to whether PostgreSQL is reachable, so the suite is meaningful both on a
machine without the server and on one where `alembic upgrade head` has run.
"""

from fastapi.testclient import TestClient

from app.db.session import Base, engine
from app.main import app

client = TestClient(app, raise_server_exceptions=False)


def test_root_returns_service_metadata():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["name"] == "DealFlow360 API"


def test_health_reports_database_state():
    response = client.get("/api/health")
    # 200 when PostgreSQL answered, 503 when it did not - never a silent 200.
    assert response.status_code in (200, 503)

    body = response.json()
    database = body["database"]

    assert database["dialect"] == "postgresql", "PostgreSQL must be the only database"
    assert database["tables_expected"] == len(Base.metadata.tables)

    if database["connected"]:
        assert body["status"] == "ok"
        assert database["server_version"]
    else:
        assert body["status"] == "degraded"


def test_health_never_leaks_the_connection_string():
    """A failed probe must report the error type, not the DSN behind it."""
    body = client.get("/api/health").text

    # No connection URL in any form, and never the credentials themselves.
    assert "://" not in body
    assert engine.url.render_as_string(hide_password=False) not in body
    assert "password" not in body.lower()
    if engine.url.username:
        assert f"{engine.url.username}:" not in body


def test_every_core_table_is_declared():
    """The schema from Step 3 must cover the full quote-to-cash flow."""
    expected = {
        "users",
        "customers",
        "products",
        "product_variants",
        "price_lists",
        "price_list_items",
        "discount_rules",
        "approval_rules",
        "warehouses",
        "inventory",
        "subscription_plans",
        "recommendation_rules",
        "quotations",
        "quotation_items",
        "approvals",
        "audit_logs",
        "fulfillment_splits",
        "backorders",
        "billing_schedules",
        "subscriptions",
        "negotiations",
        "negotiation_comments",
        "invoices",
        "invoice_items",
        "payments",
        "deal_alerts",
    }
    assert expected <= set(Base.metadata.tables)


def test_models_declare_timestamps_and_primary_keys():
    for name, table in Base.metadata.tables.items():
        assert table.primary_key.columns, f"{name} has no primary key"
        assert "created_at" in table.c, f"{name} is missing created_at"
        assert "updated_at" in table.c, f"{name} is missing updated_at"
