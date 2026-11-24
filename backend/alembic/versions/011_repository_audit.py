"""add repository_documents, audit_log; check options on checks

Revision ID: 011
Revises: 010
Create Date: 2024-01-01
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "011"
down_revision = "010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- repository_documents table ---
    op.create_table(
        "repository_documents",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("check_id", UUID(as_uuid=True), sa.ForeignKey("checks.id"), nullable=False),
        sa.Column("submitted_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("work_title", sa.String(500), nullable=True),
        sa.Column("student_name", sa.String(200), nullable=True),
        sa.Column("group_name", sa.String(200), nullable=True),
        sa.Column("word_count", sa.Integer, nullable=True),
        sa.Column("language", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_repo_docs_org_id", "repository_documents", ["org_id"])
    op.create_index("ix_repo_docs_check_id", "repository_documents", ["check_id"], unique=True)

    # --- audit_log table ---
    op.create_table(
        "audit_log",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("resource_type", sa.String(50), nullable=False),
        sa.Column("resource_id", UUID(as_uuid=True), nullable=True),
        sa.Column("details", JSONB, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_audit_log_user_id", "audit_log", ["user_id"])
    op.create_index("ix_audit_log_action", "audit_log", ["action"])
    op.create_index("ix_audit_log_created_at", "audit_log", ["created_at"])

    # --- new columns on checks ---
    op.add_column("checks", sa.Column("save_to_repository", sa.Boolean, nullable=False, server_default="false"))
    op.add_column("checks", sa.Column("excluded_sources", JSONB, nullable=False, server_default="[]"))
    op.add_column("checks", sa.Column("exclude_quotes", sa.Boolean, nullable=False, server_default="false"))
    op.add_column("checks", sa.Column("exclude_bibliography", sa.Boolean, nullable=False, server_default="true"))
    op.add_column("checks", sa.Column("min_match_words", sa.Integer, nullable=False, server_default="8"))


def downgrade() -> None:
    op.drop_column("checks", "min_match_words")
    op.drop_column("checks", "exclude_bibliography")
    op.drop_column("checks", "exclude_quotes")
    op.drop_column("checks", "excluded_sources")
    op.drop_column("checks", "save_to_repository")
    op.drop_index("ix_audit_log_created_at", "audit_log")
    op.drop_index("ix_audit_log_action", "audit_log")
    op.drop_index("ix_audit_log_user_id", "audit_log")
    op.drop_table("audit_log")
    op.drop_index("ix_repo_docs_check_id", "repository_documents")
    op.drop_index("ix_repo_docs_org_id", "repository_documents")
    op.drop_table("repository_documents")
