"""add webhook_url to checks

Revision ID: 005
Revises: 004
Create Date: 2024-01-01
"""
from alembic import op
import sqlalchemy as sa

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("checks", sa.Column("webhook_url", sa.String(2000), nullable=True))


def downgrade() -> None:
    op.drop_column("checks", "webhook_url")
