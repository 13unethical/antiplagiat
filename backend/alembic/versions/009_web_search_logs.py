"""add web_search_logs table

Revision ID: 009
Revises: 008
Create Date: 2024-01-01
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "web_search_logs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("check_id", UUID(as_uuid=True), sa.ForeignKey("checks.id"), nullable=False),
        sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("queries_count", sa.Integer, nullable=False, default=0),
        sa.Column("urls_fetched", sa.Integer, nullable=False, default=0),
        sa.Column("matches_found", sa.Integer, nullable=False, default=0),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_web_search_logs_check_id", "web_search_logs", ["check_id"])
    op.create_index("ix_web_search_logs_org_id", "web_search_logs", ["org_id"])
    op.create_index("ix_web_search_logs_created_at", "web_search_logs", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_web_search_logs_created_at", "web_search_logs")
    op.drop_index("ix_web_search_logs_org_id", "web_search_logs")
    op.drop_index("ix_web_search_logs_check_id", "web_search_logs")
    op.drop_table("web_search_logs")
