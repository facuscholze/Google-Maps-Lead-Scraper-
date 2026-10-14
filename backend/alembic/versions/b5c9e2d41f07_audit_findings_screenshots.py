"""audit evidence: findings + screenshots columns

Revision ID: b5c9e2d41f07
Revises: a3b8f5c29d1e
Create Date: 2026-10-14
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "b5c9e2d41f07"
down_revision: str | None = "a3b8f5c29d1e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("website_audits") as batch:
        batch.add_column(sa.Column("findings", sa.JSON(), nullable=False, server_default="[]"))
        batch.add_column(sa.Column("screenshots", sa.JSON(), nullable=False, server_default="[]"))


def downgrade() -> None:
    with op.batch_alter_table("website_audits") as batch:
        batch.drop_column("screenshots")
        batch.drop_column("findings")
