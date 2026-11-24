"""org default settings + api_request_log table

Revision ID: 012
Revises: 011
Create Date: 2024-01-01
"""
import sqlalchemy as sa
from alembic import op

revision = "012"
down_revision = "011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Organization default settings ────────────────────────────────────────
    op.add_column("organizations", sa.Column(
        "default_exclude_quotes", sa.Boolean(), nullable=False, server_default="true"
    ))
    op.add_column("organizations", sa.Column(
        "default_exclude_bibliography", sa.Boolean(), nullable=False, server_default="true"
    ))
    op.add_column("organizations", sa.Column(
        "default_save_to_repository", sa.Boolean(), nullable=False, server_default="false"
    ))
    op.add_column("organizations", sa.Column(
        "default_min_match_words", sa.Integer(), nullable=False, server_default="8"
    ))
    op.add_column("organizations", sa.Column(
        "require_student_name", sa.Boolean(), nullable=False, server_default="false"
    ))
    op.add_column("organizations", sa.Column(
        "require_group", sa.Boolean(), nullable=False, server_default="false"
    ))
    op.add_column("organizations", sa.Column(
        "report_footer", sa.String(255), nullable=False, server_default=""
    ))

    # ── API request log ──────────────────────────────────────────────────────
    op.create_table(
        "api_request_log",
        sa.Column("id", sa.UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("org_id", sa.UUID(), sa.ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True),
        sa.Column("api_key_id", sa.UUID(), sa.ForeignKey("api_keys.id", ondelete="SET NULL"), nullable=True),
        sa.Column("method", sa.String(10), nullable=False),
        sa.Column("path", sa.String(500), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=False),
        sa.Column("response_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("ix_api_request_log_org_id", "api_request_log", ["org_id"])
    op.create_index("ix_api_request_log_created_at", "api_request_log", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_api_request_log_created_at", "api_request_log")
    op.drop_index("ix_api_request_log_org_id", "api_request_log")
    op.drop_table("api_request_log")
    op.drop_column("organizations", "report_footer")
    op.drop_column("organizations", "require_group")
    op.drop_column("organizations", "require_student_name")
    op.drop_column("organizations", "default_min_match_words")
    op.drop_column("organizations", "default_save_to_repository")
    op.drop_column("organizations", "default_exclude_bibliography")
    op.drop_column("organizations", "default_exclude_quotes")
