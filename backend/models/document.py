"""Structured document persistence models.

These tables are the durable mirror of the in-memory :class:`DocumentNode` tree
defined in :mod:`services.document_model`. Each level of the hierarchy
(Part → Chapter → Section → Paragraph → Sentence) gets its own table so that
any single node can be fetched, edited, translated, or exported without
reloading or reparsing the whole book.

Denormalized ``project_id`` (and ``book_id`` where useful) on every level keeps
authorization and project-scoped list queries cheap, mirroring the convention
already used by ``chapters`` in ``docs/Database_Design.md``.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import GUID, Base, TimestampMixin, UUIDPrimaryKeyMixin


class Part(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Optional grouping above chapters (e.g. 'Part I: Foundations')."""

    __tablename__ = "document_parts"
    __table_args__ = (
        Index("ix_document_parts_book_id", "book_id"),
        Index("ix_document_parts_project_id", "project_id"),
        Index("ix_document_parts_position", "book_id", "position"),
        UniqueConstraint("book_id", "slug", name="uq_document_parts_book_slug"),
    )

    project_id: Mapped[UUID] = mapped_column(GUID(), ForeignKey("projects.id"), nullable=False)
    book_id: Mapped[UUID] = mapped_column(GUID(), ForeignKey("books.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    slug: Mapped[str] = mapped_column(String(320), nullable=False)
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(40), default="draft", nullable=False)
    word_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    book: Mapped[Book] = relationship(back_populates="parts")
    chapters: Mapped[list[Chapter]] = relationship(
        back_populates="part",
        cascade="all, delete-orphan",
        order_by="Chapter.position",
    )


class Chapter(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Chapter — may sit directly under a Book or under an optional Part."""

    __tablename__ = "document_chapters"
    __table_args__ = (
        Index("ix_document_chapters_book_id", "book_id"),
        Index("ix_document_chapters_project_id", "project_id"),
        Index("ix_document_chapters_part_id", "part_id"),
        Index("ix_document_chapters_position", "book_id", "position"),
        UniqueConstraint("book_id", "slug", name="uq_document_chapters_book_slug"),
    )

    project_id: Mapped[UUID] = mapped_column(GUID(), ForeignKey("projects.id"), nullable=False)
    book_id: Mapped[UUID] = mapped_column(GUID(), ForeignKey("books.id"), nullable=False)
    part_id: Mapped[UUID | None] = mapped_column(GUID(), ForeignKey("document_parts.id"))
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    slug: Mapped[str] = mapped_column(String(320), nullable=False)
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(40), default="draft", nullable=False)
    word_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # Flat prose body for the simple chapter API. The structured Section/
    # Paragraph/Sentence tree remains the source of truth for advanced editing;
    # ``content`` is a convenient denormalized field for direct chapter writing
    # and is kept in sync with ``word_count`` by the chapter service.
    content: Mapped[str] = mapped_column(Text, default="", nullable=False)

    book: Mapped[Book] = relationship(back_populates="chapters")
    part: Mapped[Part | None] = relationship(back_populates="chapters")
    sections: Mapped[list[Section]] = relationship(
        back_populates="chapter",
        cascade="all, delete-orphan",
        order_by="Section.position",
    )


class Section(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Section within a chapter (e.g. a sub-heading block)."""

    __tablename__ = "document_sections"
    __table_args__ = (
        Index("ix_document_sections_chapter_id", "chapter_id"),
        Index("ix_document_sections_project_id", "project_id"),
        Index("ix_document_sections_book_id", "book_id"),
        Index("ix_document_sections_position", "chapter_id", "position"),
    )

    project_id: Mapped[UUID] = mapped_column(GUID(), ForeignKey("projects.id"), nullable=False)
    book_id: Mapped[UUID] = mapped_column(GUID(), ForeignKey("books.id"), nullable=False)
    chapter_id: Mapped[UUID] = mapped_column(
        GUID(), ForeignKey("document_chapters.id"), nullable=False
    )
    title: Mapped[str | None] = mapped_column(String(300))
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="draft", nullable=False)
    word_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    chapter: Mapped[Chapter] = relationship(back_populates="sections")
    paragraphs: Mapped[list[Paragraph]] = relationship(
        back_populates="section",
        cascade="all, delete-orphan",
        order_by="Paragraph.position",
    )


class Paragraph(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Paragraph within a section."""

    __tablename__ = "document_paragraphs"
    __table_args__ = (
        Index("ix_document_paragraphs_section_id", "section_id"),
        Index("ix_document_paragraphs_chapter_id", "chapter_id"),
        Index("ix_document_paragraphs_project_id", "project_id"),
        Index("ix_document_paragraphs_book_id", "book_id"),
        Index("ix_document_paragraphs_position", "section_id", "position"),
    )

    project_id: Mapped[UUID] = mapped_column(GUID(), ForeignKey("projects.id"), nullable=False)
    book_id: Mapped[UUID] = mapped_column(GUID(), ForeignKey("books.id"), nullable=False)
    chapter_id: Mapped[UUID] = mapped_column(
        GUID(), ForeignKey("document_chapters.id"), nullable=False
    )
    section_id: Mapped[UUID] = mapped_column(
        GUID(), ForeignKey("document_sections.id"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String(40), default="body", nullable=False)
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="draft", nullable=False)
    word_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    section: Mapped[Section] = relationship(back_populates="paragraphs")
    sentences: Mapped[list[Sentence]] = relationship(
        back_populates="paragraph",
        cascade="all, delete-orphan",
        order_by="Sentence.position",
    )


class Sentence(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Sentence — the atomic prose leaf node that carries the actual text."""

    __tablename__ = "document_sentences"
    __table_args__ = (
        Index("ix_document_sentences_paragraph_id", "paragraph_id"),
        Index("ix_document_sentences_section_id", "section_id"),
        Index("ix_document_sentences_chapter_id", "chapter_id"),
        Index("ix_document_sentences_project_id", "project_id"),
        Index("ix_document_sentences_book_id", "book_id"),
        Index("ix_document_sentences_position", "paragraph_id", "position"),
    )

    project_id: Mapped[UUID] = mapped_column(GUID(), ForeignKey("projects.id"), nullable=False)
    book_id: Mapped[UUID] = mapped_column(GUID(), ForeignKey("books.id"), nullable=False)
    chapter_id: Mapped[UUID] = mapped_column(
        GUID(), ForeignKey("document_chapters.id"), nullable=False
    )
    section_id: Mapped[UUID] = mapped_column(
        GUID(), ForeignKey("document_sections.id"), nullable=False
    )
    paragraph_id: Mapped[UUID] = mapped_column(
        GUID(), ForeignKey("document_paragraphs.id"), nullable=False
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[str] = mapped_column(String(40), default="body", nullable=False)
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="draft", nullable=False)

    paragraph: Mapped[Paragraph] = relationship(back_populates="sentences")


from models.project import Book  # noqa: E402  (avoid circular import at top)

# Back-references ``Book.parts`` and ``Book.chapters`` are declared on the Book
# model itself (see models/project.py) so the full document hierarchy is
# traversable from a single ORM root without late attribute patching.
