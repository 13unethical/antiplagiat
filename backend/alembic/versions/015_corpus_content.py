"""store corpus content in postgres (no-docker plagiarism)

Revision ID: 015
Revises: 014
Create Date: 2024-01-01
"""
from alembic import op
import sqlalchemy as sa

revision = "015"
down_revision = "014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("corpus_documents", sa.Column("content", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("corpus_documents", "content")
