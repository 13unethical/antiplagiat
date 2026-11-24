"""add work_title student_name group_name to checks

Revision ID: 004
Revises: 003
Create Date: 2024-01-01
"""
from alembic import op
import sqlalchemy as sa

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("checks", sa.Column("work_title", sa.String(500), nullable=True))
    op.add_column("checks", sa.Column("student_name", sa.String(200), nullable=True))
    op.add_column("checks", sa.Column("group_name", sa.String(200), nullable=True))


def downgrade() -> None:
    op.drop_column("checks", "group_name")
    op.drop_column("checks", "student_name")
    op.drop_column("checks", "work_title")
