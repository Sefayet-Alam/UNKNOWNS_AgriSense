"""chat_messages.attachments column (render sent photos in the thread)

Revision ID: 0008_message_attachments
Revises: 0007_attachments
Create Date: 2026-07-25

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0008_message_attachments"
down_revision: Union[str, None] = "0007_attachments"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "chat_messages",
        sa.Column(
            "attachments",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
    )


def downgrade() -> None:
    op.drop_column("chat_messages", "attachments")
