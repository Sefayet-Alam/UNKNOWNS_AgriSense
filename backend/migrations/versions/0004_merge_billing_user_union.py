"""merge billing and user union migration branches

Revision ID: 0004_merge_billing_user_union
Revises: 0003_billing, 0003_user_union
Create Date: 2026-07-24
"""
from __future__ import annotations

from typing import Sequence, Union

revision: str = "0004_merge_billing_user_union"
down_revision: Union[str, Sequence[str], None] = (
    "0003_billing",
    "0003_user_union",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
