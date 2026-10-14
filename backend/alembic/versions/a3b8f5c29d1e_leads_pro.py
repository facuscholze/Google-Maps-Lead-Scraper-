"""leads pro: tags/owner + lead_views table

Revision ID: a3b8f5c29d1e
Revises: 9f4c2e1a7b3d
Create Date: 2026-10-14

Aditiva y reversible: dos columnas nuevas en ``leads`` (tags, owner_name) y la
tabla ``lead_views`` para vistas guardadas del workspace (Fase 4).
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a3b8f5c29d1e"
down_revision: str | None = "9f4c2e1a7b3d"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("leads", sa.Column("tags", sa.String(length=500), nullable=True))
    op.add_column("leads", sa.Column("owner_name", sa.String(length=120), nullable=True))
    with op.batch_alter_table("leads") as batch:
        batch.create_index("ix_leads_owner_name", ["owner_name"])

    op.create_table(
        "lead_views",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("config_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    with op.batch_alter_table("lead_views") as batch:
        batch.create_index("ix_lead_views_workspace_id", ["workspace_id"])
        batch.create_unique_constraint("uq_lead_views_ws_name", ["workspace_id", "name"])


def downgrade() -> None:
    op.drop_table("lead_views")
    with op.batch_alter_table("leads") as batch:
        batch.drop_index("ix_leads_owner_name")
        batch.drop_column("owner_name")
        batch.drop_column("tags")
