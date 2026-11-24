"""add mt_segments, model_versions, dataset_entries; mt_flag/stylometry on checks

Revision ID: 010
Revises: 009
Create Date: 2024-01-01
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "010"
down_revision = "009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- mt_segments table ---
    op.create_table(
        "mt_segments",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("check_id", UUID(as_uuid=True), sa.ForeignKey("checks.id"), nullable=False),
        sa.Column("start_char", sa.Integer, nullable=False),
        sa.Column("end_char", sa.Integer, nullable=False),
        sa.Column("probability", sa.Float, nullable=False),
        sa.Column("mt_kind", sa.String(50), nullable=False, server_default="generic"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_mt_segments_check_id", "mt_segments", ["check_id"])

    # --- model_versions table ---
    op.create_table(
        "model_versions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("model_type", sa.String(50), nullable=False),   # ai_detector | mt_detector
        sa.Column("version", sa.String(50), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("metrics", JSONB, nullable=False, server_default="{}"),  # fpr, tpr, auroc, f1, dataset_size
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
    )
    op.create_index("ix_model_versions_model_type", "model_versions", ["model_type"])

    # --- dataset_entries table ---
    op.create_table(
        "dataset_entries",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("dispute_id", UUID(as_uuid=True), sa.ForeignKey("disputes.id"), nullable=False),
        sa.Column("check_id", UUID(as_uuid=True), sa.ForeignKey("checks.id"), nullable=False),
        sa.Column("label", sa.String(50), nullable=False),          # human_written | ai_generated | machine_translated
        sa.Column("text_hash", sa.String(64), nullable=False),      # sha256 of normalized text, for dedup
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
    )
    op.create_index("ix_dataset_entries_text_hash", "dataset_entries", ["text_hash"], unique=True)
    op.create_index("ix_dataset_entries_label", "dataset_entries", ["label"])

    # --- new columns on checks ---
    op.add_column("checks", sa.Column("mt_flag", sa.Boolean, nullable=True))
    op.add_column("checks", sa.Column("mt_percent", sa.Float, nullable=True))
    op.add_column("checks", sa.Column("stylometry_score", sa.Float, nullable=True))


def downgrade() -> None:
    op.drop_column("checks", "stylometry_score")
    op.drop_column("checks", "mt_percent")
    op.drop_column("checks", "mt_flag")
    op.drop_index("ix_dataset_entries_label", "dataset_entries")
    op.drop_index("ix_dataset_entries_text_hash", "dataset_entries")
    op.drop_table("dataset_entries")
    op.drop_index("ix_model_versions_model_type", "model_versions")
    op.drop_table("model_versions")
    op.drop_index("ix_mt_segments_check_id", "mt_segments")
    op.drop_table("mt_segments")
