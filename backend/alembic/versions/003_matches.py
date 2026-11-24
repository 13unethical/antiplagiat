"""add corpus_documents, check_matches, similarity columns

Revision ID: 003
Revises: 002
Create Date: 2026-11-23
"""
from typing import Union, Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # corpus_documents
    op.create_table(
        "corpus_documents",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("url", sa.String(1000), nullable=True),
        sa.Column("language", sa.String(50), nullable=False, server_default=sa.text("'ru'")),
        sa.Column("source_type", sa.String(50), nullable=False, server_default=sa.text("'web'")),
        sa.Column("content_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("word_count", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("opensearch_id", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_corpus_documents_content_hash", "corpus_documents", ["content_hash"])

    # check_matches
    op.create_table(
        "check_matches",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("check_id", sa.UUID(as_uuid=True), sa.ForeignKey("checks.id"), nullable=False),
        sa.Column("corpus_doc_id", sa.UUID(as_uuid=True), sa.ForeignKey("corpus_documents.id"), nullable=True),
        sa.Column("start_char", sa.Integer, nullable=False),
        sa.Column("end_char", sa.Integer, nullable=False),
        sa.Column("matched_text", sa.Text, nullable=False),
        sa.Column("source_title", sa.String(500), nullable=False),
        sa.Column("source_url", sa.String(1000), nullable=True),
        sa.Column("source_lang", sa.String(50), nullable=False, server_default=sa.text("'ru'")),
        sa.Column("match_kind", sa.String(50), nullable=False, server_default=sa.text("'exact'")),
        sa.Column("score", sa.Float, nullable=False, server_default=sa.text("1.0")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_check_matches_check_id", "check_matches", ["check_id"])

    # Добавляем similarity-колонки в checks
    op.add_column("checks", sa.Column("similarity_percent", sa.Float, nullable=True))
    op.add_column("checks", sa.Column("similarity_sources_count", sa.Integer, nullable=True))


def downgrade() -> None:
    op.drop_column("checks", "similarity_sources_count")
    op.drop_column("checks", "similarity_percent")
    op.drop_table("check_matches")
    op.drop_table("corpus_documents")
