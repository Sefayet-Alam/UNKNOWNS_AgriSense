"""users: add union_name/union_code to the registration address

Revision ID: 0003_user_union
Revises: 0002_farms
Create Date: 2026-07-24
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003_user_union"
down_revision: Union[str, None] = "0002_farms"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("union_name", sa.String(length=80), nullable=False, server_default=""),
    )
    op.add_column(
        "users",
        sa.Column("union_code", sa.String(length=12), nullable=False, server_default=""),
    )


def downgrade() -> None:
    op.drop_column("users", "union_code")
    op.drop_column("users", "union_name")
