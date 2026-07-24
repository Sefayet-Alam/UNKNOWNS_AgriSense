"""persist BDApps CaaS sandbox receipts

Revision ID: 0011_caas_sandbox_transactions
Revises: 0010_merge_market_research
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0011_caas_sandbox_transactions"
down_revision: Union[str, None] = "0010_merge_market_research"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "caas_transactions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.String(length=64), nullable=False),
        sa.Column("external_trx_id", sa.String(length=80), nullable=False),
        sa.Column("internal_trx_id", sa.String(length=80), nullable=False),
        sa.Column("reference_id", sa.String(length=80), nullable=False),
        sa.Column("amount_bdt", sa.Integer(), nullable=False),
        sa.Column("balance_before_bdt", sa.Integer(), nullable=False),
        sa.Column("balance_after_bdt", sa.Integer(), nullable=False),
        sa.Column("status_code", sa.String(length=16), nullable=False),
        sa.Column("status_detail", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("external_trx_id"),
        sa.UniqueConstraint("internal_trx_id"),
        sa.UniqueConstraint("reference_id"),
    )
    op.create_index("ix_caas_transactions_user_id", "caas_transactions", ["user_id"])
    op.create_index("ix_caas_transactions_external_trx_id", "caas_transactions", ["external_trx_id"])


def downgrade() -> None:
    op.drop_index("ix_caas_transactions_external_trx_id", table_name="caas_transactions")
    op.drop_index("ix_caas_transactions_user_id", table_name="caas_transactions")
    op.drop_table("caas_transactions")
