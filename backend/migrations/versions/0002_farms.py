"""farms table (farm-scoped profile for the planning workflow)

Revision ID: 0002_farms
Revises: 0001_initial
Create Date: 2026-07-24

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002_farms"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "farms",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("division_name", sa.String(length=80), nullable=False),
        sa.Column("division_code", sa.String(length=8), nullable=False),
        sa.Column("district_name", sa.String(length=80), nullable=False),
        sa.Column("district_code", sa.String(length=8), nullable=False),
        sa.Column("upazila_name", sa.String(length=80), nullable=False),
        sa.Column("upazila_code", sa.String(length=12), nullable=False),
        sa.Column("union_name", sa.String(length=80), nullable=False),
        sa.Column("union_geocode", sa.String(length=12), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("area_decimal", sa.Float(), nullable=True),
        sa.Column("original_area_value", sa.Float(), nullable=True),
        sa.Column("original_area_unit", sa.String(length=24), nullable=False),
        sa.Column("area_conversion_note", sa.String(length=255), nullable=False),
        sa.Column("land_type", sa.String(length=40), nullable=False),
        sa.Column("soil_texture", sa.String(length=40), nullable=False),
        sa.Column("soil_test", sa.JSON(), nullable=True),
        sa.Column("irrigation_available", sa.Boolean(), nullable=True),
        sa.Column("water_source", sa.String(length=80), nullable=False),
        sa.Column("budget_bdt", sa.BigInteger(), nullable=True),
        sa.Column("season", sa.String(length=20), nullable=False),
        sa.Column("previous_crop", sa.String(length=60), nullable=False),
        sa.Column("risk_tolerance", sa.String(length=12), nullable=False),
        sa.Column("preferred_crops", sa.JSON(), nullable=False),
        sa.Column("excluded_crops", sa.JSON(), nullable=False),
        sa.Column("phase", sa.String(length=30), nullable=False),
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
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_farms_user_id", "farms", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_farms_user_id", table_name="farms")
    op.drop_table("farms")
