"""add technician presences

Revision ID: 818f1f44f7e9
Revises: e4f2ef64bb6a
Create Date: 2026-04-13 16:25:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "818f1f44f7e9"
down_revision: Union[str, Sequence[str], None] = "e4f2ef64bb6a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "technician_presences",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("technician_id", sa.Integer(), nullable=False),
        sa.Column("is_logged_in", sa.Boolean(), nullable=False),
        sa.Column("session_started_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["technician_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("technician_id"),
    )
    op.create_index(
        op.f("ix_technician_presences_technician_id"),
        "technician_presences",
        ["technician_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_technician_presences_technician_id"), table_name="technician_presences")
    op.drop_table("technician_presences")
