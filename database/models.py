import uuid
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import String, Text, Integer, Boolean, ForeignKey, DateTime, UniqueConstraint, Float, Index
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
    series_metadata: Mapped[Optional["SeriesMetadata"]] = relationship(
        back_populates="series", uselist=False, cascade="all, delete-orphan"
    )
    arcs: Mapped[List["StoryArc"]] = relationship(
        back_populates="series", cascade="all, delete-orphan", order_by="StoryArc.start_chapter"
    )
    sources: Mapped[List["SeriesSource"]] = relationship(
        back_populates="series", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Series(title={self.title})>"


class SeriesSource(Base, TimestampMixin):
    """Tracks where the manga is being pulled from and any numbering offsets."""
    __tablename__ = "series_sources"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    series_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("series.id", ondelete="CASCADE"), nullable=False)
    
    url: Mapped[str] = mapped_column(Text, nullable=False)
    # Canonical_Chapter = Source_Chapter + chapter_offset
    chapter_offset: Mapped[float] = mapped_column(Float, default=0.0)
    
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    priority: Mapped[int] = mapped_column(Integer, default=1) # 1 is primary
    
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Relationships
    series: Mapped["Series"] = relationship(back_populates="sources")

    # Composite Index for optimized source discovery
    __table_args__ = (
        Index("idx_source_lookup", "series_id", "is_active", "priority"),
    )

    def __repr__(self) -> str:
        return f"<SeriesSource(series_id={self.series_id}, url={self.url[:30]}...)>"


class SeriesMetadata(Base, TimestampMixin):
    __tablename__ = "series_metadata"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    series_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("series.id", ondelete="CASCADE"), nullable=False, unique=True)
    
    is_backlog_processed: Mapped[bool] = mapped_column(Boolean, default=False)
    
    series: Mapped["Series"] = relationship(back_populates="series_metadata")

    def __repr__(self) -> str:
        return f"<SeriesMetadata(series_id={self.series_id})>"


class Chapter(Base, TimestampMixin):
    __tablename__ = "chapters"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    series_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("series.id", ondelete="CASCADE"), nullable=False)
    
    chapter_number: Mapped[float] = mapped_column(Float, nullable=False)

    # Stores the direct link to the specific chapter reader page
    url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    series: Mapped["Series"] = relationship(back_populates="chapters")
    
    summary: Mapped[Optional["Summary"]] = relationship(
        back_populates="chapter", uselist=False, cascade="all, delete-orphan"
    )
    processing: Mapped[Optional["ChapterProcessing"]] = relationship(
        back_populates="chapter", uselist=False, cascade="all, delete-orphan"
    )
    ocr_result: Mapped[Optional["OCRResult"]] = relationship(
        back_populates="chapter", uselist=False, cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("series_id", "chapter_number", name="uq_series_chapter"),
        Index("idx_chapter_url", "url"),
    )

    def __repr__(self) -> str:
        return f"<Chapter(number={self.chapter_number}, series_id={self.series_id})>"


class ChapterProcessing(Base, TimestampMixin):
    __tablename__ = "chapter_processing"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    chapter_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("chapters.id", ondelete="CASCADE"), nullable=False, unique=True)
    
    ocr_extracted: Mapped[bool] = mapped_column(Boolean, default=False)
    summary_complete: Mapped[bool] = mapped_column(Boolean, default=False)
    has_error: Mapped[bool] = mapped_column(Boolean, default=False) 

    chapter: Mapped["Chapter"] = relationship(back_populates="processing")

    # Composite Index to optimize worker queues finding pending tasks
    __table_args__ = (
        Index("idx_processing_status", "ocr_extracted", "summary_complete", "has_error"),
    )

    def __repr__(self) -> str:
        return f"<ChapterProcessing(chapter_id={self.chapter_id}, ocr={self.ocr_extracted}, summary={self.summary_complete})>"


class Summary(Base, TimestampMixin):
    __tablename__ = "summaries"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    chapter_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("chapters.id", ondelete="CASCADE"), nullable=False, unique=True)
    
    content: Mapped[str] = mapped_column(Text, nullable=False) 
    
    chapter: Mapped["Chapter"] = relationship(back_populates="summary")

    def __repr__(self) -> str:
        return f"<Summary(chapter_id={self.chapter_id})>"


class OCRResult(Base, TimestampMixin):
    __tablename__ = "ocr_results"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    chapter_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("chapters.id", ondelete="CASCADE"), nullable=False, unique=True)
    
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)

    chapter: Mapped["Chapter"] = relationship(back_populates="ocr_result", uselist=False)

    def __repr__(self) -> str:
        return f"<OCRResult(chapter_id={self.chapter_id})>"


class StoryArc(Base, TimestampMixin):
    __tablename__ = "story_arcs"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    series_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("series.id", ondelete="CASCADE"), nullable=False)
    
    arc_title: Mapped[str] = mapped_column(String(255), nullable=False)
    
    start_chapter: Mapped[float] = mapped_column(Float, nullable=False)
    end_chapter: Mapped[float] = mapped_column(Float, nullable=False)
    
    arc_summary: Mapped[str] = mapped_column(Text, nullable=False) 
    
    series: Mapped["Series"] = relationship(back_populates="arcs")

    def __repr__(self) -> str:
        return f"<StoryArc(title={self.arc_title}, chapters={self.start_chapter}-{self.end_chapter})>"