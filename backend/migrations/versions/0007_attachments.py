"""attachments table (Tier 2: leaf photo + voice note uploads)

Revision ID: 0007_attachments
Revises: 0006_merge_kb_bdapps
Create Date: 2026-07-25

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0007_attachments"
down_revision: Union[str, None] = "0006_merge_kb_bdapps"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "attachments",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("mime_type", sa.String(length=80), nullable=False),
        sa.Column("path", sa.String(length=400), nullable=False),
        sa.Column("transcript", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_attachments_user_id", "attachments", ["user_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_attachments_user_id", table_name="attachments")
    op.drop_table("attachments")
