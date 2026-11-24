"""add ai_percent and ai_model_version to checks

Revision ID: 008
Revises: 007
Create Date: 2024-01-01
"""
from alembic import op
import sqlalchemy as sa

revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("checks", sa.Column("ai_percent", sa.Float, nullable=True))
    op.add_column("checks", sa.Column("ai_model_version", sa.String(50), nullable=True))


def downgrade() -> None:
    op.drop_column("checks", "ai_model_version")
    op.drop_column("checks", "ai_percent")
