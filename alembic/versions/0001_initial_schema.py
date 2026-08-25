"""initial schema: users, judgments, chunks, citations, saved_searches

Revision ID: 0001
Revises:
Create Date: 2026-08-26

"""
from collections.abc import Sequence

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")  # gen_random_uuid()

    op.create_table(
        "users",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("hashed_password", sa.String(), nullable=True),
        sa.Column("full_name", sa.String(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("email"),
    )

    op.create_table(
        "judgments",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column("source_dataset", sa.String(), nullable=False),
        sa.Column("source_url", sa.String(), nullable=True),
        sa.Column("external_id", sa.String(), nullable=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("court", sa.String(), nullable=True),
        sa.Column("case_type", sa.String(), nullable=True),
        sa.Column("decision_date", sa.Date(), nullable=True),
        sa.Column("judges", postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column("petitioner", sa.Text(), nullable=True),
        sa.Column("respondent", sa.Text(), nullable=True),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column(
            "text_tsv",
            postgresql.TSVECTOR(),
            sa.Computed(
                "to_tsvector('english', coalesce(title, '') || ' ' || raw_text)", persisted=True
            ),
            nullable=True,
        ),
        sa.Column("language", sa.String(), nullable=False, server_default="en"),
        sa.Column("ingestion_status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("source_dataset", "external_id"),
    )
    op.create_index("judgments_text_tsv_gin", "judgments", ["text_tsv"], postgresql_using="gin")
    op.create_index("judgments_court_idx", "judgments", ["court"])
    op.create_index("judgments_decision_date_idx", "judgments", ["decision_date"])

    op.create_table(
        "chunks",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column(
            "judgment_id",
            sa.BigInteger(),
            sa.ForeignKey("judgments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column(
            "text_tsv",
            postgresql.TSVECTOR(),
            sa.Computed("to_tsvector('english', text)", persisted=True),
            nullable=True,
        ),
        sa.Column("embedding", Vector(384), nullable=True),
        sa.Column("embedding_model", sa.String(), nullable=False, server_default="all-MiniLM-L6-v2"),
        sa.Column("token_count", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("judgment_id", "chunk_index"),
    )
    op.create_index("chunks_text_tsv_gin", "chunks", ["text_tsv"], postgresql_using="gin")
    op.create_index("chunks_judgment_id_idx", "chunks", ["judgment_id"])

    op.create_table(
        "citations",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column(
            "citing_judgment_id",
            sa.BigInteger(),
            sa.ForeignKey("judgments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "cited_judgment_id",
            sa.BigInteger(),
            sa.ForeignKey("judgments.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("cited_text", sa.Text(), nullable=False),
        sa.Column("citation_type", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("citing_judgment_id <> cited_judgment_id"),
    )
    op.create_index("citations_citing_idx", "citations", ["citing_judgment_id"])
    op.create_index("citations_cited_idx", "citations", ["cited_judgment_id"])

    op.create_table(
        "saved_searches",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("query_text", sa.Text(), nullable=False),
        sa.Column("filters", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("saved_searches_user_id_idx", "saved_searches", ["user_id"])


def downgrade() -> None:
    op.drop_table("saved_searches")
    op.drop_table("citations")
    op.drop_table("chunks")
    op.drop_table("judgments")
    op.drop_table("users")
