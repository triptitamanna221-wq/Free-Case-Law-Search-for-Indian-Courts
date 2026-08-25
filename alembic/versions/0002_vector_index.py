"""HNSW index on chunks.embedding

Built as a separate, explicit migration from the schema DDL in 0001: HNSW build
cost should be paid once, deliberately, not on every routine schema change while
the table is still small/empty during early development.

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-26

"""
from collections.abc import Sequence

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "CREATE INDEX chunks_embedding_hnsw ON chunks "
        "USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS chunks_embedding_hnsw")
