import uuid
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import String, Text, Integer, Boolean, ForeignKey, DateTime, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

# -------------------------------------------------------------------------
# Base & Mixins
# -------------------------------------------------------------------------

class Base(DeclarativeBase):
    """Abstract base class for all models."""
    pass

class TimestampMixin:
    """Automatically handles created_at and updated_at timestamps."""
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

# -------------------------------------------------------------------------
# Models
# -------------------------------------------------------------------------

class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)

    def __repr__(self) -> str:
        return f"<User(username={self.username})>"


class Series(Base, TimestampMixin):
    __tablename__ = "series"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(255), nullable=False)

    # Relationships
    chapters: Mapped[List["Chapter"]] = relationship(
        back_populates="series", cascade="all, delete-orphan", order_by="Chapter.chapter_number"
    )
    # UPDATE: Renamed from 'metadata' to 'series_metadata' to avoid SQLAlchemy reserved keyword
    series_metadata: Mapped[Optional["SeriesMetadata"]] = relationship(
        back_populates="series", uselist=False, cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Series(title={self.title})>"


class SeriesMetadata(Base, TimestampMixin):
    __tablename__ = "series_metadata"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    series_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("series.id", ondelete="CASCADE"), nullable=False, unique=True)
    
    # Track overall series pipeline status (e.g., initial bulk scrape finished)
    is_backlog_processed: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Relationships
    # UPDATE: Matches the newly renamed relationship in Series
    series: Mapped["Series"] = relationship(back_populates="series_metadata")

    def __repr__(self) -> str:
        return f"<SeriesMetadata(series_id={self.series_id})>"


class Chapter(Base, TimestampMixin):
    __tablename__ = "chapters"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    series_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("series.id", ondelete="CASCADE"), nullable=False)
    chapter_number: Mapped[int] = mapped_column(Integer, nullable=False)

    # Relationships
    series: Mapped["Series"] = relationship(back_populates="chapters")
    
    summary: Mapped[Optional["Summary"]] = relationship(
        back_populates="chapter", uselist=False, cascade="all, delete-orphan"
    )
    # 1-to-1 relationship to the processing pipeline tracker
    processing: Mapped[Optional["ChapterProcessing"]] = relationship(
        back_populates="chapter", uselist=False, cascade="all, delete-orphan"
    )

    ocr_result: Mapped[Optional["OCRResult"]] = relationship(
        back_populates="chapter", uselist=False, cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("series_id", "chapter_number", name="uq_series_chapter"),
    )

    def __repr__(self) -> str:
        return f"<Chapter(number={self.chapter_number}, series_id={self.series_id})>"


class ChapterProcessing(Base, TimestampMixin):
    __tablename__ = "chapter_processing"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    chapter_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("chapters.id", ondelete="CASCADE"), nullable=False, unique=True)
    
    # Pipeline States
    ocr_extracted: Mapped[bool] = mapped_column(Boolean, default=False)
    summary_complete: Mapped[bool] = mapped_column(Boolean, default=False)
    has_error: Mapped[bool] = mapped_column(Boolean, default=False) # Useful if a worker fails

    # Relationships
    chapter: Mapped["Chapter"] = relationship(back_populates="processing")

    def __repr__(self) -> str:
        return f"<ChapterProcessing(chapter_id={self.chapter_id}, ocr={self.ocr_extracted}, summary={self.summary_complete})>"


class Summary(Base, TimestampMixin):
    __tablename__ = "summaries"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    chapter_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("chapters.id", ondelete="CASCADE"), nullable=False, unique=True)
    
    content: Mapped[str] = mapped_column(Text, nullable=False) 
    
    # Relationships
    chapter: Mapped["Chapter"] = relationship(back_populates="summary")

    def __repr__(self) -> str:
        return f"<Summary(chapter_id={self.chapter_id})>"

class OCRResult(Base, TimestampMixin):
    __tablename__ = "ocr_results"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    chapter_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("chapters.id", ondelete="CASCADE"), 
        nullable=False, 
        unique=True
    )
    
    # The 'Vault' for the raw text
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)

    # Relationships
    chapter: Mapped["Chapter"] = relationship(back_populates="ocr_result", uselist=False)

    def __repr__(self) -> str:
        return f"<OCRResult(chapter_id={self.chapter_id})>"