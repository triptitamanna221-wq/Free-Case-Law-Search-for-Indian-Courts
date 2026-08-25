from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    ARRAY,
    CheckConstraint,
    Computed,
    Date,
    DateTime,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base

if TYPE_CHECKING:
    from app.db.models.chunk import Chunk


class Judgment(Base):
    __tablename__ = "judgments"
    __table_args__ = (UniqueConstraint("source_dataset", "external_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    source_dataset: Mapped[str] = mapped_column(String, nullable=False)
    source_url: Mapped[str | None] = mapped_column(String, nullable=True)
    external_id: Mapped[str | None] = mapped_column(String, nullable=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    court: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    case_type: Mapped[str | None] = mapped_column(String, nullable=True)
    decision_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    judges: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    petitioner: Mapped[str | None] = mapped_column(Text, nullable=True)
    respondent: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    # GENERATED ALWAYS AS ... STORED at the DB level (see alembic/versions/0001).
    # Computed() here isn't DDL authority (Alembic already created the real
    # column) -- it exists purely so the ORM excludes text_tsv from INSERT/UPDATE
    # statements, matching Postgres' refusal to accept an explicit value for it.
    text_tsv: Mapped[str | None] = mapped_column(
        TSVECTOR, Computed("to_tsvector('english', coalesce(title, '') || ' ' || raw_text)"),
        nullable=True, deferred=True,
    )
    language: Mapped[str] = mapped_column(String, nullable=False, default="en")
    ingestion_status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    chunks: Mapped[list["Chunk"]] = relationship(
        back_populates="judgment", cascade="all, delete-orphan"
    )


class Citation(Base):
    __tablename__ = "citations"
    __table_args__ = (CheckConstraint("citing_judgment_id <> cited_judgment_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    citing_judgment_id: Mapped[int] = mapped_column(
        ForeignKey("judgments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    cited_judgment_id: Mapped[int | None] = mapped_column(
        ForeignKey("judgments.id", ondelete="SET NULL"), nullable=True, index=True
    )
    cited_text: Mapped[str] = mapped_column(Text, nullable=False)
    citation_type: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
