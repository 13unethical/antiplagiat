"""webhook_secret + LTI platforms/submissions

Revision ID: 016
Revises: 015
Create Date: 2026-11-27
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "016"
down_revision = "015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "organizations",
        sa.Column("webhook_secret", sa.String(128), nullable=True),
    )

    op.create_table(
        "lti_platforms",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("platform_type", sa.String(50), nullable=False, server_default="canvas"),
        sa.Column("issuer", sa.String(500), nullable=False),
        sa.Column("client_id", sa.String(255), nullable=False),
        sa.Column("deployment_ids", JSONB, nullable=False, server_default="[]"),
        sa.Column("jwks_url", sa.String(1000), nullable=True),
        sa.Column("auth_login_url", sa.String(1000), nullable=True),
        sa.Column("auth_token_url", sa.String(1000), nullable=True),
        sa.Column("api_base_url", sa.String(1000), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_lti_platforms_org_id", "lti_platforms", ["org_id"])
    op.create_index("ix_lti_platforms_issuer_client", "lti_platforms", ["issuer", "client_id"])

    op.create_table(
        "lti_submissions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("platform_id", UUID(as_uuid=True), sa.ForeignKey("lti_platforms.id", ondelete="CASCADE"), nullable=False),
        sa.Column("check_id", UUID(as_uuid=True), sa.ForeignKey("checks.id", ondelete="SET NULL"), nullable=True),
        sa.Column("external_assignment_id", sa.String(255), nullable=False),
        sa.Column("external_submission_id", sa.String(255), nullable=False),
        sa.Column("student_lms_id", sa.String(255), nullable=True),
        sa.Column("student_name", sa.String(255), nullable=True),
        sa.Column("report_status", sa.String(50), nullable=False, server_default="pending"),
        sa.Column("canvas_report_url", sa.String(2000), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_lti_submissions_platform_id", "lti_submissions", ["platform_id"])
    op.create_index("ix_lti_submissions_check_id", "lti_submissions", ["check_id"])
    op.create_index(
        "ix_lti_submissions_ext",
        "lti_submissions",
        ["platform_id", "external_assignment_id", "external_submission_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_table("lti_submissions")
    op.drop_table("lti_platforms")
    op.drop_column("organizations", "webhook_secret")
