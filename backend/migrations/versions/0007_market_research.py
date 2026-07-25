"""retain the legacy local market-research revision

Revision ID: 0007_market_research
Revises: 0006_merge_kb_bdapps
"""
from typing import Sequence, Union

revision: str = "0007_market_research"
down_revision: Union[str, None] = "0006_merge_kb_bdapps"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Historical marker: legacy market tables already exist on affected DBs."""


def downgrade() -> None:
    """Historical marker only; do not remove retained market tables."""
