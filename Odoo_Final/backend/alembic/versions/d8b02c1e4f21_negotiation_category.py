"""add category_id to negotiation requests

Revision ID: d8b02c1e4f21
Revises: c7a91e4b2d10
Create Date: 2026-09-05 20:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "d8b02c1e4f21"
down_revision: Union[str, None] = "c7a91e4b2d10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("negotiation_requests", sa.Column("category_id", sa.Integer(), nullable=True))
    op.create_index("ix_negotiation_requests_category_id", "negotiation_requests", ["category_id"])
    op.create_foreign_key(
        "fk_negotiation_requests_category_id_product_categories",
        "negotiation_requests",
        "product_categories",
        ["category_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_negotiation_requests_category_id_product_categories", "negotiation_requests", type_="foreignkey")
    op.drop_index("ix_negotiation_requests_category_id", table_name="negotiation_requests")
    op.drop_column("negotiation_requests", "category_id")
