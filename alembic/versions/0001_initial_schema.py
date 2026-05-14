"""initial schema

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-05-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("username", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_telegram_id"), "users", ["telegram_id"], unique=True)

    op.create_table(
        "recipe_results",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(length=16), nullable=False),
        sa.Column("source_url", sa.String(length=512), nullable=True),
        sa.Column("detected_ingredients", sa.Text(), nullable=False),
        sa.Column("recipe_titles", sa.Text(), nullable=False),
        sa.Column("from_cache", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_recipe_results_user_id"), "recipe_results", ["user_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_recipe_results_user_id"), table_name="recipe_results")
    op.drop_table("recipe_results")
    op.drop_index(op.f("ix_users_telegram_id"), table_name="users")
    op.drop_table("users")
