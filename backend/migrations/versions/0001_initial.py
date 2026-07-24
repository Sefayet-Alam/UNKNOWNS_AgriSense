"""initial schema

Creates the pgvector extension and all five tables (users, token_blacklist,
chat_sessions, chat_messages, long_term_memory) exactly matching
``app.models`` as of the initial scaffold.

Revision ID: 0001_initial
Revises:
Create Date: 2026-07-24

"""
from __future__ import annotations

from typing import Sequence, Union

import pgvector.sqlalchemy
import sqlalchemy as sa
from alembic import op

from app.config import settings

# revision identifiers, used by Alembic.
revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # pgvector extension MUST exist before the Vector column is created.
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # ---- users ---------------------------------------------------------- #
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("username", sa.String(length=150), nullable=False),
        sa.Column("phone", sa.String(length=20), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("division_name", sa.String(length=80), nullable=False),
        sa.Column("division_code", sa.String(length=8), nullable=False),
        sa.Column("district_name", sa.String(length=80), nullable=False),
        sa.Column("district_code", sa.String(length=8), nullable=False),
        sa.Column("upazila_name", sa.String(length=80), nullable=False),
        sa.Column("upazila_code", sa.String(length=12), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_username", "users", ["username"], unique=False)
    op.create_index("ix_users_phone", "users", ["phone"], unique=True)

    # ---- token_blacklist ------------------------------------------------ #
    op.create_table(
        "token_blacklist",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("jti", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_token_blacklist_jti", "token_blacklist", ["jti"], unique=True
    )

    # ---- chat_sessions -------------------------------------------------- #
    op.create_table(
        "chat_sessions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("summary_upto_id", sa.BigInteger(), nullable=False),
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
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_chat_sessions_user_id", "chat_sessions", ["user_id"], unique=False
    )

    # ---- chat_messages -------------------------------------------------- #
    op.create_table(
        "chat_messages",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("tool_trace", sa.JSON(), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["session_id"], ["chat_sessions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_chat_messages_session_id_id",
        "chat_messages",
        ["session_id", "id"],
        unique=False,
    )

    # ---- long_term_memory (pgvector) ------------------------------------ #
    op.create_table(
        "long_term_memory",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "embedding",
            pgvector.sqlalchemy.Vector(dim=settings.EMBEDDING_DIM),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_long_term_memory_user_id",
        "long_term_memory",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_long_term_memory_user_id", table_name="long_term_memory")
    op.drop_table("long_term_memory")

    op.drop_index(
        "ix_chat_messages_session_id_id", table_name="chat_messages"
    )
    op.drop_table("chat_messages")

    op.drop_index("ix_chat_sessions_user_id", table_name="chat_sessions")
    op.drop_table("chat_sessions")

    op.drop_index("ix_token_blacklist_jti", table_name="token_blacklist")
    op.drop_table("token_blacklist")

    op.drop_index("ix_users_phone", table_name="users")
    op.drop_index("ix_users_username", table_name="users")
    op.drop_table("users")

    # Leave the pgvector extension in place; dropping it is a cluster-wide
    # concern and other databases/objects may depend on it.
