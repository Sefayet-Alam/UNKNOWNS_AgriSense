"""merge legacy market-research and current application schema branches

Revision ID: 0010_merge_market_research
Revises: 0009_season_plans_weather_alerts, 0007_market_research
"""
from typing import Sequence, Union


revision: str = "0010_merge_market_research"
down_revision: Union[str, Sequence[str], None] = (
    "0009_season_plans_weather_alerts",
    "0007_market_research",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Merge marker; Alembic applies the missing current-schema branch first."""


def downgrade() -> None:
    """Merge marker only."""
