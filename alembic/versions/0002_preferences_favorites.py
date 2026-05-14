"""preferences and favorites

Revision ID: 0002_preferences_favorites
Revises: 0001_initial_schema
Create Date: 2026-05-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_preferences_favorites"
down_revision: str | None = "0001_initial_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("recipe_results", sa.Column("recipe_payload", sa.Text(), nullable=True))

    op.create_table(
        "user_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("nutrition_enabled", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("dietary_style", sa.String(length=32), server_default="balanced", nullable=False),
        sa.Column("avoid_ingredients", sa.Text(), server_default="[]", nullable=False),
        sa.Column("default_servings", sa.Integer(), server_default="2", nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_user_settings_user_id"), "user_settings", ["user_id"], unique=True)

    op.create_table(
        "favorite_recipes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("source_result_id", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("recipe_payload", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["source_result_id"], ["recipe_results.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_favorite_recipes_user_id"), "favorite_recipes", ["user_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_favorite_recipes_user_id"), table_name="favorite_recipes")
    op.drop_table("favorite_recipes")
    op.drop_index(op.f("ix_user_settings_user_id"), table_name="user_settings")
    op.drop_table("user_settings")
    op.drop_column("recipe_results", "recipe_payload")
