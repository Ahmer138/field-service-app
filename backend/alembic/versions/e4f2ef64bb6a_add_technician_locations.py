"""add technician locations

Revision ID: e4f2ef64bb6a
Revises: 88731d15ba05
Create Date: 2026-04-13 15:55:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e4f2ef64bb6a"
down_revision: Union[str, Sequence[str], None] = "88731d15ba05"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "technician_locations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("technician_id", sa.Integer(), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("accuracy_meters", sa.Float(), nullable=True),
        sa.Column("recorded_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["technician_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_technician_locations_recorded_at"),
        "technician_locations",
        ["recorded_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_technician_locations_technician_id"),
        "technician_locations",
        ["technician_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_technician_locations_technician_id"), table_name="technician_locations")
    op.drop_index(op.f("ix_technician_locations_recorded_at"), table_name="technician_locations")
    op.drop_table("technician_locations")
