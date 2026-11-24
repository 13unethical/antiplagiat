"""add checks, check_documents, check_flags tables

Revision ID: 002
Revises: 001
Create Date: 2026-11-23
"""
from typing import Union, Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "checks",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", sa.UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("submitted_by", sa.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("filename", sa.String(500), nullable=False),
        sa.Column("file_size", sa.BigInteger, nullable=False, server_default=sa.text("0")),
        sa.Column("file_path", sa.String(1000), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("word_count", sa.Integer, nullable=True),
        sa.Column("language", sa.String(50), nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "check_documents",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("check_id", sa.UUID(as_uuid=True), sa.ForeignKey("checks.id"), nullable=False),
        sa.Column("raw_text", sa.Text, nullable=False),
        sa.Column("normalized_text", sa.Text, nullable=False),
        sa.Column(
            "position_map",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("check_id", name="uq_check_documents_check_id"),
    )

    op.create_table(
        "check_flags",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("check_id", sa.UUID(as_uuid=True), sa.ForeignKey("checks.id"), nullable=False),
        sa.Column("type", sa.String(100), nullable=False),
        sa.Column("severity", sa.String(50), nullable=False),
        sa.Column("count", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column(
            "details",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    op.create_index("ix_checks_org_id", "checks", ["org_id"])
    op.create_index("ix_checks_submitted_by", "checks", ["submitted_by"])
    op.create_index("ix_check_flags_check_id", "check_flags", ["check_id"])


def downgrade() -> None:
    op.drop_table("check_flags")
    op.drop_table("check_documents")
    op.drop_table("checks")
