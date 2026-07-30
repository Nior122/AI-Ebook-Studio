"""Writing Engine — produces structured DocumentNode trees, never plain text.

Every AI call goes through :class:`WritingEngine` and returns typed, uniquely-
identified :class:`DocumentNode` subtrees instead of raw prose strings.

This is what makes the Editing, Images, Translation, DOCX, and KDP Validator
modules possible without reparsing: they all receive a :class:`DocumentNode`
subtree (identified by node id) and mutate it in place.

Usage::

    engine = WritingEngine(ai_engine)
    doc = await engine.generate_chapter(doc, chapter_id, context={"topic": "..."})
    # doc.chapters() now contains fully structured sections/paragraphs/sentences
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, cast
from uuid import UUID

import structlog
from sqlalchemy import delete

from providers.ai.base import GenerationConfig, GenerationRequest, GenerationResponse, Message
from services.document_model import (
    DocumentModelError,
    DocumentNode,
    DocumentNodeType,
    StructuredDocument,
    node,
)
from services.prompt_engine import PromptEngine

logger = structlog.get_logger(__name__)

# Maximum sentences per paragraph before the engine starts a new paragraph.
_MAX_SENTENCES_PER_PARAGRAPH = 8


# ---------------------------------------------------------------------------
# prompt templates — registered in _register_prompts
# ---------------------------------------------------------------------------

_OUTLINE_SYSTEM = (
    "You are a professional book outline generator. "
    "Always respond with valid JSON matching the requested schema. "
    "Never include markdown fences, explanations, or commentary outside the JSON."
)

_OUTLINE_USER = (
    "Generate a detailed book outline for a {genre} book titled '{title}'.\n\n"
    "Context about the book:\n{context}\n\n"
    "Return a JSON array of chapter objects. Each chapter has:\n"
    '- "title": string (chapter title)\n'
    '- "summary": string (2-3 sentence summary of the chapter)\n'
    '- "sections": array of objects with "title" (section heading) and '
    '"description" (what the section covers)\n\n'
    "Aim for 8-15 chapters with 2-5 sections per chapter."
)

_CHAPTER_SYSTEM = (
    "You are an expert {genre} author. "
    "Write prose that is engaging, well-structured, and appropriate for the "
    "target audience. Always respond with valid JSON matching the requested "
    "schema. Never include markdown fences or commentary outside the JSON."
)

_CHAPTER_USER = (
    "Write the content for chapter '{chapter_title}' of a '{genre}' book "
    "titled '{book_title}'.\n\n"
    "Chapter summary: {chapter_summary}\n\n"
    "Sections to write:\n{section_descriptions}\n\n"
    "Writing style guidance:\n{writing_style}\n\n"
    "Target audience: {target_audience}\n\n"
    "Return a JSON object with a single key 'sections' which is an array of "
    "section objects. Each section object has:\n"
    '- "title": string (section heading)\n'
    '- "paragraphs": array of paragraph objects, each with:\n'
    '    - "kind": "body" | "dialogue" | "quote" | "list" | "transition"\n'
    '    - "sentences": array of strings (individual sentences)\n\n'
    "Each paragraph should have 2-{max_sentences} sentences. "
    "Write complete, publication-ready prose."
)

_SECTION_SYSTEM = _CHAPTER_SYSTEM  # same system prompt

_SECTION_USER = (
    "Write the content for section '{section_title}' of chapter "
    "'{chapter_title}' in the book '{book_title}'.\n\n"
    "Section description: {section_description}\n\n"
    "Context from surrounding sections:\n"
    "Previous section: {previous_section}\n"
    "Next section: {next_section}\n\n"
    "Writing style: {writing_style}\n\n"
    "Return a JSON array of paragraph objects. Each paragraph has:\n"
    '- "kind": "body" | "dialogue" | "quote" | "list" | "transition"\n'
    '- "sentences": array of strings (individual sentences)\n\n'
    "Each paragraph should have 2-{max_sentences} sentences. "
    "Write complete, publication-ready prose."
)

_REWRITE_SYSTEM = (
    "You are an expert editor. Revise the provided text according to the "
    "instruction while preserving meaning and tone. "
    "Respond with valid JSON only."
)

_REWRITE_USER = (
    "Rewrite the following paragraph according to this instruction: "
    '"{instruction}"\n\n'
    "Current text:\n{text}\n\n"
    "Return a JSON object with a single key 'sentences' which is an array of "
    "strings, each string being one revised sentence."
)


# ---------------------------------------------------------------------------
# Writing Engine
# ---------------------------------------------------------------------------


@dataclass
class WritingEngine:
    """Produces structured document trees via AI generation.

    Wraps :class:`AIEngine` with structured-output prompts that produce
    typed, uniquely-identified document nodes instead of raw text.
    """

    ai_engine: Any  # AIEngine — typed as Any to avoid import cycle at model level
    prompt_engine: PromptEngine = field(default_factory=PromptEngine)
    _logger: structlog.stdlib.BoundLogger = field(
        default_factory=lambda: structlog.get_logger(__name__)
    )

    def __post_init__(self) -> None:
        self._register_prompts()

    # ------------------------------------------------------------------
    # public generation API
    # ------------------------------------------------------------------

    async def generate_outline(
        self,
        project_id: UUID,
        book_id: UUID,
        book_title: str,
        genre: str = "nonfiction",
        context: str = "",
    ) -> StructuredDocument:
        """Generate a chapter/section outline and return a structured document.

        This is the entry point for a new book: it produces the part/chapter/
        section hierarchy without prose content.
        """
        doc = StructuredDocument.new_book(project_id, book_id, book_title)
        system, user = self.prompt_engine.build_messages(
            prompt_name="generate_outline",
            context={
                "title": book_title,
                "genre": genre,
                "context": context,
            },
        )
        response = await self._call_ai(system, user)
        outline_data = self._parse_json(response.text)
        chapter_nodes = (
            outline_data if isinstance(outline_data, list) else outline_data.get("chapters", [])
        )

        for ch_data in chapter_nodes:
            chapter_node = node(
                "chapter",
                title=ch_data.get("title", "Untitled Chapter"),
                status="outline",
            )
            chapter_node.metadata["summary"] = ch_data.get("summary", "")
            doc.root.add_child(chapter_node)

            for sec_data in ch_data.get("sections", []):
                section_node = node(
                    "section",
                    title=sec_data.get("title", "Untitled Section"),
                    status="planned",
                )
                section_node.metadata["description"] = sec_data.get("description", "")
                chapter_node.add_child(section_node)

        self._logger.info(
            "outline_generated",
            project_id=str(project_id),
            book_id=str(book_id),
            chapter_count=len(doc.chapters()),
        )
        return doc

    async def generate_chapter(
        self,
        doc: StructuredDocument,
        chapter_id: UUID,
        *,
        genre: str = "nonfiction",
        book_title: str | None = None,
        writing_style: str = "clear and accessible",
        target_audience: str = "general readers",
    ) -> StructuredDocument:
        """Fill a chapter node with Sections → Paragraphs → Sentences.

        The chapter must already exist in the outline (from ``generate_outline``
        or a prior call). Its ``sections`` children will be populated with
        prose.
        """
        chapter = doc.require(chapter_id)
        if chapter.node_type != DocumentNodeType.CHAPTER:
            raise DocumentModelError(f"Node {chapter_id} is not a chapter.")

        book_node = doc.root
        book_title = book_title or book_node.title or "Untitled"

        section_descriptions = (
            "\n".join(
                f"- {s.title}: {s.metadata.get('description', '')}"
                for s in chapter.children
                if s.node_type == DocumentNodeType.SECTION
            )
            or "No sections defined."
        )

        system, user = self.prompt_engine.build_messages(
            prompt_name="write_chapter",
            context={
                "chapter_title": chapter.title or "Untitled",
                "genre": genre,
                "book_title": book_title,
                "chapter_summary": chapter.metadata.get("summary", ""),
                "section_descriptions": section_descriptions,
                "writing_style": writing_style,
                "target_audience": target_audience,
                "max_sentences": str(_MAX_SENTENCES_PER_PARAGRAPH),
            },
        )
        response = await self._call_ai(system, user)
        sections_data = self._parse_json(response.text)

        if isinstance(sections_data, dict) and "sections" in sections_data:
            sections_data = sections_data["sections"]

        self._populate_sections(chapter, sections_data)
        chapter.status = "draft"

        self._logger.info(
            "chapter_generated",
            chapter_id=str(chapter_id),
            section_count=len(sections_data),
        )
        return doc

    async def generate_section(
        self,
        doc: StructuredDocument,
        section_id: UUID,
        *,
        chapter_title: str = "",
        book_title: str = "",
        writing_style: str = "clear and accessible",
    ) -> StructuredDocument:
        """Fill a section node with Paragraphs → Sentences.

        Useful when only one section needs to be (re)generated instead of
        the whole chapter.
        """
        section_node = doc.require(section_id)
        if section_node.node_type != DocumentNodeType.SECTION:
            raise DocumentModelError(f"Node {section_id} is not a section.")

        chapter = doc.require(section_node.parent_id) if section_node.parent_id else None
        siblings = chapter.children if chapter else []
        idx = next((i for i, s in enumerate(siblings) if s.id == section_id), -1)

        prev_title = siblings[idx - 1].title if idx > 0 and siblings else "None"
        next_title = siblings[idx + 1].title if idx < len(siblings) - 1 and siblings else "None"

        system, user = self.prompt_engine.build_messages(
            prompt_name="write_section",
            context={
                "section_title": section_node.title or "Untitled",
                "chapter_title": chapter_title or (chapter.title if chapter else "Untitled"),
                "book_title": book_title or "Untitled",
                "section_description": section_node.metadata.get("description", ""),
                "previous_section": prev_title,
                "next_section": next_title,
                "writing_style": writing_style,
                "max_sentences": str(_MAX_SENTENCES_PER_PARAGRAPH),
            },
        )
        response = await self._call_ai(system, user)
        paragraphs_data = self._parse_json(response.text)

        self._populate_paragraphs(section_node, paragraphs_data)
        section_node.status = "draft"

        return doc

    async def rewrite_paragraph(
        self,
        doc: StructuredDocument,
        paragraph_id: UUID,
        instruction: str,
    ) -> StructuredDocument:
        """Rewrite a single paragraph via AI, preserving node id and position.

        The Editing module calls this to revise specific paragraphs without
        touching the rest of the document.
        """
        para = doc.require(paragraph_id)
        if para.node_type != DocumentNodeType.PARAGRAPH:
            raise DocumentModelError(f"Node {paragraph_id} is not a paragraph.")

        current_text = para.plain_text()

        system, user = self.prompt_engine.build_messages(
            prompt_name="rewrite_paragraph",
            context={"text": current_text, "instruction": instruction},
        )
        response = await self._call_ai(system, user)
        rewrite_data = self._parse_json(response.text)

        sentences_data = (
            rewrite_data if isinstance(rewrite_data, list) else rewrite_data.get("sentences", [])
        )
        para.children.clear()
        for pos, sentence_text in enumerate(sentences_data):
            para.add_child(
                node(
                    "sentence",
                    text=sentence_text.strip(),
                    position=pos,
                )
            )

        para.status = "draft"
        self._logger.info("paragraph_rewritten", paragraph_id=str(paragraph_id))
        return doc

    async def rewrite_sentence(
        self,
        doc: StructuredDocument,
        sentence_id: UUID,
        instruction: str,
    ) -> StructuredDocument:
        """Rewrite a single sentence, preserving node id and position."""
        sent = doc.require(sentence_id)
        if sent.node_type != DocumentNodeType.SENTENCE:
            raise DocumentModelError(f"Node {sentence_id} is not a sentence.")

        system, user = self.prompt_engine.build_messages(
            prompt_name="rewrite_sentence",
            context={
                "text": sent.text or "",
                "instruction": f"Rewrite this sentence: {instruction}",
            },
        )
        response = await self._call_ai(system, user)
        rewrite_data = self._parse_json(response.text)

        sentences_raw = (
            rewrite_data
            if isinstance(rewrite_data, list)
            else rewrite_data.get("sentences", [sent.text or ""])
        )
        sent.text = sentences_raw[0].strip() if sentences_raw else sent.text
        sent.status = "draft"

        return doc

    # ------------------------------------------------------------------
    # persistence bridge — load/store the document tree
    # ------------------------------------------------------------------

    @staticmethod
    async def load_from_db(
        session: Any,  # AsyncSession
        book_id: UUID,
        project_id: UUID,
    ) -> StructuredDocument | None:
        """Hydrate a :class:`StructuredDocument` from the normalized DB tables.

        Returns ``None`` if the book has no document rows yet.
        """
        from models.document import Chapter as ChapterModel
        from models.document import Paragraph as ParagraphModel
        from models.document import Part as PartModel
        from models.document import Section as SectionModel
        from models.document import Sentence as SentenceModel
        from models.project import Book

        book = await session.get(Book, book_id)
        if book is None:
            return None

        doc_root = node("book", id=book.id, title=book.title, status=book.status)
        doc = StructuredDocument(project_id=project_id, book_id=book_id, root=doc_root)

        # Load parts
        parts_result = await session.execute(
            session.query(PartModel)
            .filter(PartModel.book_id == book_id, PartModel.deleted_at.is_(None))
            .order_by(PartModel.position)
        )
        for part_row in parts_result.scalars().all():
            part_node = node(
                "part",
                id=part_row.id,
                title=part_row.title,
                position=part_row.position,
                status=part_row.status,
            )
            part_node.metadata["summary"] = part_row.summary or ""
            doc_root.add_child(part_node)

        # Load chapters
        chapters_result = await session.execute(
            session.query(ChapterModel)
            .filter(ChapterModel.book_id == book_id, ChapterModel.deleted_at.is_(None))
            .order_by(ChapterModel.position)
        )
        for ch_row in chapters_result.scalars().all():
            ch_node = node(
                "chapter",
                id=ch_row.id,
                title=ch_row.title,
                position=ch_row.position,
                status=ch_row.status,
            )
            ch_node.metadata["summary"] = ch_row.summary or ""
            if ch_row.part_id:
                found_part_node = doc_root.find(ch_row.part_id)
                if found_part_node:
                    found_part_node.add_child(ch_node)
                else:
                    doc_root.add_child(ch_node)
            else:
                doc_root.add_child(ch_node)

        # Load sections
        sections_result = await session.execute(
            session.query(SectionModel)
            .filter(SectionModel.book_id == book_id, SectionModel.deleted_at.is_(None))
            .order_by(SectionModel.position)
        )
        for sec_row in sections_result.scalars().all():
            sec_node = node(
                "section",
                id=sec_row.id,
                title=sec_row.title or "",
                position=sec_row.position,
                status=sec_row.status,
            )
            ch_parent = doc_root.find(sec_row.chapter_id)
            if ch_parent:
                ch_parent.add_child(sec_node)

        # Load paragraphs
        para_result = await session.execute(
            session.query(ParagraphModel)
            .filter(ParagraphModel.book_id == book_id, ParagraphModel.deleted_at.is_(None))
            .order_by(ParagraphModel.position)
        )
        for para_row in para_result.scalars().all():
            para_node = node(
                "paragraph",
                id=para_row.id,
                kind=para_row.kind,
                position=para_row.position,
                status=para_row.status,
            )
            sec_parent = doc_root.find(para_row.section_id)
            if sec_parent:
                sec_parent.add_child(para_node)

        # Load sentences
        sent_result = await session.execute(
            session.query(SentenceModel)
            .filter(SentenceModel.book_id == book_id, SentenceModel.deleted_at.is_(None))
            .order_by(SentenceModel.position)
        )
        for sent_row in sent_result.scalars().all():
            sent_node = node(
                "sentence",
                id=sent_row.id,
                text=sent_row.text,
                kind=sent_row.kind,
                position=sent_row.position,
                status=sent_row.status,
            )
            para_parent = doc_root.find(sent_row.paragraph_id)
            if para_parent:
                para_parent.add_child(sent_node)

        return doc

    @staticmethod
    async def save_to_db(
        session: Any,  # AsyncSession
        doc: StructuredDocument,
    ) -> None:
        """Persist a :class:`StructuredDocument` to the normalized DB tables.

        This is a full-sync: it deletes existing document rows for the book
        and recreates them from the tree. For incremental saves, mutate
        individual table rows directly via the repository layer.
        """
        from models.document import Chapter as ChapterModel
        from models.document import Paragraph as ParagraphModel
        from models.document import Part as PartModel
        from models.document import Section as SectionModel
        from models.document import Sentence as SentenceModel

        book_id = doc.book_id
        project_id = doc.project_id

        # Clear existing document rows for this book
        await session.execute(delete(SentenceModel).where(SentenceModel.book_id == book_id))
        await session.execute(delete(ParagraphModel).where(ParagraphModel.book_id == book_id))
        await session.execute(delete(SectionModel).where(SectionModel.book_id == book_id))
        await session.execute(delete(ChapterModel).where(ChapterModel.book_id == book_id))
        await session.execute(delete(PartModel).where(PartModel.book_id == book_id))

        part_map: dict[UUID, PartModel] = {}
        chapter_map: dict[UUID, ChapterModel] = {}
        section_map: dict[UUID, SectionModel] = {}
        paragraph_map: dict[UUID, ParagraphModel] = {}

        for node_item in doc.walk():
            if node_item.id == doc.root.id:
                continue

            if node_item.node_type == DocumentNodeType.PART:
                part_row = PartModel(
                    id=node_item.id,
                    project_id=project_id,
                    book_id=book_id,
                    title=node_item.title or "",
                    slug=node_item.title or f"part-{node_item.position}",
                    position=node_item.position,
                    summary=node_item.metadata.get("summary"),
                    status=node_item.status,
                    word_count=node_item.word_count(),
                )
                session.add(part_row)
                part_map[node_item.id] = part_row

            elif node_item.node_type == DocumentNodeType.CHAPTER:
                ch_row = ChapterModel(
                    id=node_item.id,
                    project_id=project_id,
                    book_id=book_id,
                    part_id=node_item.parent_id if node_item.parent_id in part_map else None,
                    title=node_item.title or "",
                    slug=node_item.title or f"chapter-{node_item.position}",
                    position=node_item.position,
                    summary=node_item.metadata.get("summary"),
                    status=node_item.status,
                    word_count=node_item.word_count(),
                )
                session.add(ch_row)
                chapter_map[node_item.id] = ch_row

            elif node_item.node_type == DocumentNodeType.SECTION:
                sec_row = SectionModel(
                    id=node_item.id,
                    project_id=project_id,
                    book_id=book_id,
                    chapter_id=node_item.parent_id or UUID(int=0),
                    title=node_item.title,
                    position=node_item.position,
                    status=node_item.status,
                    word_count=node_item.word_count(),
                )
                session.add(sec_row)
                section_map[node_item.id] = sec_row

            elif node_item.node_type == DocumentNodeType.PARAGRAPH:
                ancestor_chapter_id = _find_ancestor_id(
                    node_item, DocumentNodeType.CHAPTER, doc.root
                )
                para_row = ParagraphModel(
                    id=node_item.id,
                    project_id=project_id,
                    book_id=book_id,
                    chapter_id=ancestor_chapter_id or UUID(int=0),
                    section_id=node_item.parent_id or UUID(int=0),
                    kind=node_item.kind or "body",
                    position=node_item.position,
                    status=node_item.status,
                    word_count=node_item.word_count(),
                )
                session.add(para_row)
                paragraph_map[node_item.id] = para_row

            elif node_item.node_type == DocumentNodeType.SENTENCE:
                sent_chapter_id = _find_ancestor_id(node_item, DocumentNodeType.CHAPTER, doc.root)
                sent_section_id = _find_ancestor_id(node_item, DocumentNodeType.SECTION, doc.root)
                sent_row = SentenceModel(
                    id=node_item.id,
                    project_id=project_id,
                    book_id=book_id,
                    chapter_id=sent_chapter_id or UUID(int=0),
                    section_id=sent_section_id or UUID(int=0),
                    paragraph_id=node_item.parent_id or UUID(int=0),
                    text=node_item.text or "",
                    kind=node_item.kind or "body",
                    position=node_item.position,
                    status=node_item.status,
                )
                session.add(sent_row)

        await session.commit()

    # ------------------------------------------------------------------
    # internals
    # ------------------------------------------------------------------

    def _register_prompts(self) -> None:
        self.prompt_engine.register(
            "generate_outline",
            system=_OUTLINE_SYSTEM,
            user=_OUTLINE_USER,
            default_version="1.0.0",
            variables=("title", "genre", "context"),
        )
        self.prompt_engine.register(
            "write_chapter",
            system=_CHAPTER_SYSTEM,
            user=_CHAPTER_USER,
            default_version="1.0.0",
            variables=(
                "chapter_title",
                "genre",
                "book_title",
                "chapter_summary",
                "section_descriptions",
                "writing_style",
                "target_audience",
                "max_sentences",
            ),
        )
        self.prompt_engine.register(
            "write_section",
            system=_SECTION_SYSTEM,
            user=_SECTION_USER,
            default_version="1.0.0",
            variables=(
                "section_title",
                "chapter_title",
                "book_title",
                "section_description",
                "previous_section",
                "next_section",
                "writing_style",
                "max_sentences",
            ),
        )
        self.prompt_engine.register(
            "rewrite_paragraph",
            system=_REWRITE_SYSTEM,
            user=_REWRITE_USER,
            default_version="1.0.0",
            variables=("text", "instruction"),
        )
        self.prompt_engine.register(
            "rewrite_sentence",
            system=_REWRITE_SYSTEM,
            user=_REWRITE_USER,
            default_version="1.0.0",
            variables=("text", "instruction"),
        )

    async def _call_ai(self, system: str | None, user: str | None) -> GenerationResponse:
        messages: list[Message] = []
        if system:
            messages.append(Message(role="system", content=system))
        if user:
            messages.append(Message(role="user", content=user))

        request = GenerationRequest(
            messages=messages,
            model=self.ai_engine._default_provider_name() + "/gpt-4o-mini",
            config=GenerationConfig(
                temperature=0.7,
                json_mode=True,
                retry_attempts=1,
            ),
        )
        response = await self.ai_engine.generate(request)
        return cast(GenerationResponse, response)

    @staticmethod
    def _parse_json(text: str) -> Any:
        """Parse a JSON string, stripping markdown fences if present."""
        cleaned = text.strip()
        if cleaned.startswith("```"):
            _, *rest = cleaned.split("\n", 1)
            if rest:
                cleaned = rest[-1]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3].strip()
        return json.loads(cleaned)

    @staticmethod
    def _populate_sections(
        chapter_node: DocumentNode,
        sections_data: list[dict[str, Any]],
    ) -> None:
        for sec_data in sections_data:
            title = sec_data.get("title", "Untitled Section")
            existing = [
                c
                for c in chapter_node.children
                if c.node_type == DocumentNodeType.SECTION and c.title == title
            ]
            if existing:
                section_node = existing[0]
            else:
                section_node = node("section", title=title)
                chapter_node.add_child(section_node)

            for para_data in sec_data.get("paragraphs", []):
                para_node = node(
                    "paragraph",
                    kind=para_data.get("kind", "body"),
                )
                section_node.add_child(para_node)
                for pos, sentence_text in enumerate(para_data.get("sentences", [])):
                    para_node.add_child(node("sentence", text=sentence_text.strip(), position=pos))

    @staticmethod
    def _populate_paragraphs(
        section_node: DocumentNode,
        paragraphs_data: list[dict[str, Any]],
    ) -> None:
        for para_data in paragraphs_data:
            para_node = node(
                "paragraph",
                kind=para_data.get("kind", "body"),
            )
            section_node.add_child(para_node)
            for pos, sentence_text in enumerate(para_data.get("sentences", [])):
                para_node.add_child(node("sentence", text=sentence_text.strip(), position=pos))


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _find_ancestor_id(
    node_item: DocumentNode,
    ancestor_type: DocumentNodeType,
    root: DocumentNode,
) -> UUID | None:
    """Walk up from *node_item* to find the nearest ancestor of *ancestor_type*."""
    if node_item.parent_id is None:
        return None
    parent = root.find(node_item.parent_id)
    while parent is not None:
        if parent.node_type == ancestor_type:
            return parent.id
        if parent.parent_id is None:
            return None
        parent = root.find(parent.parent_id)
    return None
