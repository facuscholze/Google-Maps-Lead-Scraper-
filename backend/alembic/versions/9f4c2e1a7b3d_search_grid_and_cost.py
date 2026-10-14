"""search grid mode, budget and api cost accounting

Revision ID: 9f4c2e1a7b3d
Revises: 18c7f2b699b6
Create Date: 2026-10-14 16:30:00.000000

Adds the columns the Phase-2 search engine needs: search mode (text|grid),
geo spec, budget cap, API usage/cost accounting, grid progress counters and
cooperative cancellation. Purely additive — existing rows keep defaults.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "9f4c2e1a7b3d"
down_revision: Union[str, None] = "18c7f2b699b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("searches", sa.Column("mode", sa.String(length=10), nullable=False, server_default="text"))
    op.add_column("searches", sa.Column("geo_json", sa.JSON(), nullable=True))
    op.add_column("searches", sa.Column("budget_cap_usd", sa.Float(), nullable=True))
    op.add_column("searches", sa.Column("estimated_api_calls", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("searches", sa.Column("estimated_cost_usd", sa.Float(), nullable=True))
    op.add_column("searches", sa.Column("api_calls", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("searches", sa.Column("api_cost_usd", sa.Float(), nullable=False, server_default="0"))
    op.add_column("searches", sa.Column("budget_exhausted", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("searches", sa.Column("grid_total_cells", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("searches", sa.Column("grid_done_cells", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("searches", sa.Column("grid_capped_cells", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("searches", sa.Column("deduped_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("searches", sa.Column("cancel_requested", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    op.drop_column("searches", "cancel_requested")
    op.drop_column("searches", "deduped_count")
    op.drop_column("searches", "grid_capped_cells")
    op.drop_column("searches", "grid_done_cells")
    op.drop_column("searches", "grid_total_cells")
    op.drop_column("searches", "budget_exhausted")
    op.drop_column("searches", "api_cost_usd")
    op.drop_column("searches", "api_calls")
    op.drop_column("searches", "estimated_cost_usd")
    op.drop_column("searches", "estimated_api_calls")
    op.drop_column("searches", "budget_cap_usd")
    op.drop_column("searches", "geo_json")
    op.drop_column("searches", "mode")
