from datetime import datetime
from typing import TYPE_CHECKING

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.ingestion.embedder import EMBEDDING_DIM, EMBEDDING_MODEL_NAME

if TYPE_CHECKING:
    from app.db.models.judgment import Judgment


class Chunk(Base):
    __tablename__ = "chunks"
    __table_args__ = (UniqueConstraint("judgment_id", "chunk_index"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    judgment_id: Mapped[int] = mapped_column(
        ForeignKey("judgments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    text_tsv: Mapped[str | None] = mapped_column(TSVECTOR, nullable=True, deferred=True)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM), nullable=True)
    embedding_model: Mapped[str] = mapped_column(String, nullable=False, default=EMBEDDING_MODEL_NAME)
    token_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    judgment: Mapped["Judgment"] = relationship(back_populates="chunks")
