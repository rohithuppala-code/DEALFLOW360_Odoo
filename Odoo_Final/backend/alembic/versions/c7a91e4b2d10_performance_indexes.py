"""performance indexes for deal workflow queries

Revision ID: c7a91e4b2d10
Revises: b62f14c3396b
Create Date: 2026-09-05 18:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "c7a91e4b2d10"
down_revision: Union[str, None] = "b62f14c3396b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

INDEXES = [
    ("ix_quotes_status_sales_rep", "quotes", ["status", "sales_rep_id"]),
    ("ix_quotes_customer_status", "quotes", ["customer_id", "status"]),
    ("ix_quotes_approval_status", "quotes", ["approval_status"]),
    ("ix_quotes_health_score", "quotes", ["deal_health_score"]),
    ("ix_quotes_updated_at", "quotes", ["updated_at"]),
    ("ix_quote_lines_product_id", "quote_lines", ["product_id"]),
    ("ix_quote_lines_warehouse_id", "quote_lines", ["warehouse_id"]),
    ("ix_notifications_user_unread", "notifications", ["user_id", "is_read", "created_at"]),
    ("ix_customers_status", "customers", ["status"]),
    ("ix_customers_name", "customers", ["name"]),
    ("ix_customers_sales_rep_id", "customers", ["sales_rep_id"]),
    ("ix_approval_steps_status_role", "approval_steps", ["status", "role"]),
    ("ix_subscriptions_status", "subscriptions", ["status"]),
    ("ix_subscriptions_next_bill", "subscriptions", ["next_billing_date"]),
    ("ix_invoices_due_date", "invoices", ["due_date"]),
    ("ix_negotiations_status", "negotiations", ["status"]),
    ("ix_products_is_active", "products", ["is_active"]),
]


def _index_exists(name: str, table: str) -> bool:
    bind = op.get_bind()
    count = bind.execute(
        sa.text(
            "SELECT COUNT(*) FROM information_schema.statistics "
            "WHERE table_schema = DATABASE() AND table_name = :t AND index_name = :n"
        ),
        {"t": table, "n": name},
    ).scalar()
    return bool(count)


def upgrade() -> None:
    for name, table, cols in INDEXES:
        if not _index_exists(name, table):
            op.create_index(name, table, cols)


def downgrade() -> None:
    for name, table, _cols in reversed(INDEXES):
        if _index_exists(name, table):
            op.drop_index(name, table_name=table)
