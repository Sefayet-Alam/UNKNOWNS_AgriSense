"""season_plans + weather_alerts (persisted calendars, proactive advisories)

Revision ID: 0007_season_plans_weather_alerts
Revises: 0006_merge_kb_bdapps
Create Date: 2026-07-25

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0007_season_plans_weather_alerts"
down_revision: Union[str, None] = "0006_merge_kb_bdapps"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "season_plans",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("farm_id", sa.Integer(), nullable=False),
        sa.Column("crop_name", sa.String(length=60), nullable=False),
        sa.Column("crop_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=12), nullable=False),
        sa.Column("planting_date", sa.Date(), nullable=False),
        sa.Column("harvest_date", sa.Date(), nullable=False),
        sa.Column("duration_days", sa.Integer(), nullable=False),
        sa.Column("selected_variety", sa.JSON(), nullable=True),
        sa.Column("calendar", sa.JSON(), nullable=False),
        sa.Column("financial_projection", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["farm_id"], ["farms.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_season_plans_farm_id", "season_plans", ["farm_id"])

    op.create_table(
        "weather_alerts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("farm_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("season_plan_id", sa.Integer(), nullable=True),
        sa.Column("alert_type", sa.String(length=30), nullable=False),
        sa.Column("event_date", sa.Date(), nullable=True),
        sa.Column("trigger_date", sa.Date(), nullable=False),
        sa.Column("message", sa.String(length=480), nullable=False),
        sa.Column("sms_status", sa.String(length=16), nullable=False),
        sa.Column("sms_response", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["farm_id"], ["farms.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["season_plan_id"], ["season_plans.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_weather_alerts_farm_id", "weather_alerts", ["farm_id"])
    op.create_index("ix_weather_alerts_user_id", "weather_alerts", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_weather_alerts_user_id", table_name="weather_alerts")
    op.drop_index("ix_weather_alerts_farm_id", table_name="weather_alerts")
    op.drop_table("weather_alerts")
    op.drop_index("ix_season_plans_farm_id", table_name="season_plans")
    op.drop_table("season_plans")
