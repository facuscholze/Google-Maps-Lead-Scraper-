"""scoring config per workspace (Fase 6)

Revision ID: c7f3a19bd5e2
Revises: b5c9e2d41f07
Create Date: 2026-10-14
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "c7f3a19bd5e2"
down_revision: str | None = "b5c9e2d41f07"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "scoring_configs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("weights_json", sa.JSON(), nullable=False),
        sa.Column("hot_min", sa.Integer(), nullable=False, server_default="80"),
        sa.Column("warm_min", sa.Integer(), nullable=False, server_default="60"),
        sa.Column("cold_min", sa.Integer(), nullable=False, server_default="40"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("workspace_id", name="uq_scoring_config_ws"),
    )


def downgrade() -> None:
    op.drop_table("scoring_configs")
