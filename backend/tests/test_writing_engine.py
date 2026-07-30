"""Tests for the Writing Engine (services.writing_engine).

Uses a mock AI provider so tests are fast, deterministic, and offline.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import uuid4

import pytest

from services.document_model import DocumentNodeType, StructuredDocument, node
from services.writing_engine import WritingEngine


@dataclass
class MockGenerationResponse:
    """Simulates a generation response with pre-canned JSON text."""

    text: str
    finish_reason: str | None = "stop"
    provider: str = "mock"
    model: str = "mock/model"
    usage: Any = None
    latency_ms: float = 0.0
    estimated_cost_usd: float = 0.0
    raw_response: dict[str, Any] | None = None


class MockAIEngine:
    """AIEngine stand-in that returns canned responses."""

    def __init__(self, responses: list[str] | None = None) -> None:
        self.call_count = 0
        self._responses = responses or []

    def _default_provider_name(self) -> str:
        return "mock"

    def add_response(self, json_text: str) -> None:
        self._responses.append(json_text)

    async def generate(self, request: Any) -> MockGenerationResponse:
        if self.call_count >= len(self._responses):
            text = '{"sections": []}'
        else:
            text = self._responses[self.call_count]
        self.call_count += 1
        return MockGenerationResponse(text=text)


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_engine() -> MockAIEngine:
    return MockAIEngine()


@pytest.fixture()
def writer(mock_engine: MockAIEngine) -> WritingEngine:
    return WritingEngine(ai_engine=mock_engine)


# ---------------------------------------------------------------------------
# generate_outline
# ---------------------------------------------------------------------------


class TestGenerateOutline:
    OUTLINE_RESPONSE = """[
        {
            "title": "Introduction",
            "summary": "Sets the stage for the topic.",
            "sections": [
                {"title": "Why This Matters", "description": "Explains relevance."},
                {"title": "What You Will Learn", "description": "Roadmap of the book."}
            ]
        },
        {
            "title": "Core Concepts",
            "summary": "Foundational ideas explained clearly.",
            "sections": [
                {"title": "First Principle", "description": "The basic building block."}
            ]
        }
    ]"""

    async def test_generates_outline(
        self, writer: WritingEngine, mock_engine: MockAIEngine
    ) -> None:
        mock_engine.add_response(self.OUTLINE_RESPONSE)
        project_id = uuid4()
        book_id = uuid4()

        doc = await writer.generate_outline(
            project_id=project_id,
            book_id=book_id,
            book_title="Test Book",
            genre="nonfiction",
        )

        assert doc.project_id == project_id
        assert doc.book_id == book_id
        assert doc.root.node_type == DocumentNodeType.BOOK

        chapters = doc.chapters()
        assert len(chapters) == 2
        assert chapters[0].title == "Introduction"
        assert chapters[1].title == "Core Concepts"

        # Check sections under the first chapter
        sections = doc.sections(chapters[0].id)
        assert len(sections) == 2
        assert sections[0].title == "Why This Matters"
        assert sections[0].metadata.get("description") == "Explains relevance."

    async def test_outline_status(self, writer: WritingEngine, mock_engine: MockAIEngine) -> None:
        mock_engine.add_response(self.OUTLINE_RESPONSE)

        doc = await writer.generate_outline(
            project_id=uuid4(),
            book_id=uuid4(),
            book_title="Test",
        )
        for ch in doc.chapters():
            assert ch.status == "outline"
            for sec in doc.sections(ch.id):
                assert sec.status == "planned"


# ---------------------------------------------------------------------------
# generate_chapter
# ---------------------------------------------------------------------------


class TestGenerateChapter:
    CHAPTER_RESPONSE = """{
        "sections": [
            {
                "title": "Why This Matters",
                "paragraphs": [
                    {
                        "kind": "body",
                        "sentences": [
                            "This is the first sentence.",
                            "This is the second sentence.",
                            "This is the third sentence."
                        ]
                    },
                    {
                        "kind": "body",
                        "sentences": [
                            "Another paragraph opens here.",
                            "It continues with more detail."
                        ]
                    }
                ]
            },
            {
                "title": "What You Will Learn",
                "paragraphs": [
                    {
                        "kind": "body",
                        "sentences": [
                            "A single sentence paragraph."
                        ]
                    }
                ]
            }
        ]
    }"""

    async def test_populates_chapter(
        self, writer: WritingEngine, mock_engine: MockAIEngine
    ) -> None:
        doc = await self._make_outline(writer, mock_engine)
        mock_engine.add_response(self.CHAPTER_RESPONSE)
        chapter_id = doc.chapters()[0].id

        doc = await writer.generate_chapter(doc, chapter_id)

        sections = doc.sections(chapter_id)
        assert len(sections) == 2

        first_section = sections[0]
        assert first_section.title == "Why This Matters"

        paragraphs = doc.paragraphs(first_section.id)
        assert len(paragraphs) == 2

        # Check sentences in first paragraph
        sentences = doc.sentences(paragraphs[0].id)
        assert len(sentences) == 3
        assert sentences[0].text == "This is the first sentence."
        assert sentences[1].text == "This is the second sentence."

        # Check chapter status updated
        assert doc.require(chapter_id).status == "draft"

    async def test_second_section_content(
        self, writer: WritingEngine, mock_engine: MockAIEngine
    ) -> None:
        doc = await self._make_outline(writer, mock_engine)
        mock_engine.add_response(self.CHAPTER_RESPONSE)
        chapter_id = doc.chapters()[0].id
        doc = await writer.generate_chapter(doc, chapter_id)

        sections = doc.sections(chapter_id)
        second_section = sections[1]
        assert second_section.title == "What You Will Learn"

        paragraphs = doc.paragraphs(second_section.id)
        assert len(paragraphs) == 1

        sentences = doc.sentences(paragraphs[0].id)
        assert len(sentences) == 1
        assert sentences[0].text == "A single sentence paragraph."

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    @staticmethod
    async def _make_outline(writer: WritingEngine, engine: MockAIEngine) -> StructuredDocument:
        outline = """[
            {"title": "Introduction", "summary": "Sets the stage.",
             "sections": [
                 {"title": "Why This Matters", "description": "Explains relevance."},
                 {"title": "What You Will Learn", "description": "Roadmap."}
             ]}
        ]"""
        engine.add_response(outline)
        return await writer.generate_outline(uuid4(), uuid4(), "Test", "nonfiction")


# ---------------------------------------------------------------------------
# generate_section
# ---------------------------------------------------------------------------


class TestGenerateSection:
    SECTION_RESPONSE = """[
        {
            "kind": "body",
            "sentences": [
                "This is the single section content.",
                "It has two sentences."
            ]
        }
    ]"""

    async def test_generates_section(
        self, writer: WritingEngine, mock_engine: MockAIEngine
    ) -> None:
        doc = await self._make_outline_with_section(writer, mock_engine)
        mock_engine.add_response(self.SECTION_RESPONSE)
        chapter_id = doc.chapters()[0].id
        section_id = doc.sections(chapter_id)[0].id

        doc = await writer.generate_section(
            doc,
            section_id,
            chapter_title="Introduction",
            book_title="Test",
        )

        paragraphs = doc.paragraphs(section_id)
        assert len(paragraphs) == 1

        sentences = doc.sentences(paragraphs[0].id)
        assert len(sentences) == 2
        assert sentences[0].text == "This is the single section content."

    @staticmethod
    async def _make_outline_with_section(
        writer: WritingEngine, engine: MockAIEngine
    ) -> StructuredDocument:
        outline = """[
            {"title": "Introduction", "summary": "Sets the stage.",
             "sections": [
                 {"title": "My Section", "description": "A test section."}
             ]}
        ]"""
        engine.add_response(outline)
        return await writer.generate_outline(uuid4(), uuid4(), "Test", "nonfiction")


# ---------------------------------------------------------------------------
# rewrite_paragraph
# ---------------------------------------------------------------------------


class TestRewriteParagraph:
    REWRITE_RESPONSE = """{
        "sentences": [
            "This is the rewritten version.",
            "It now has two polished sentences."
        ]
    }"""

    async def test_rewrites_paragraph(
        self, writer: WritingEngine, mock_engine: MockAIEngine
    ) -> None:
        doc = await self._make_doc_with_paragraph(writer, mock_engine)
        mock_engine.add_response(self.REWRITE_RESPONSE)

        chapter_id = doc.chapters()[0].id
        section_id = doc.sections(chapter_id)[0].id
        para_id = doc.paragraphs(section_id)[0].id

        original_sentences = doc.sentences(para_id)
        assert len(original_sentences) == 1
        assert original_sentences[0].text == "Original text."

        doc = await writer.rewrite_paragraph(doc, para_id, "Make it better")

        new_sentences = doc.sentences(para_id)
        assert len(new_sentences) == 2
        assert new_sentences[0].text == "This is the rewritten version."
        assert new_sentences[1].text == "It now has two polished sentences."

    @staticmethod
    async def _make_doc_with_paragraph(
        writer: WritingEngine, engine: MockAIEngine
    ) -> StructuredDocument:
        outline = """[
            {"title": "Ch1", "summary": "Test.",
             "sections": [
                 {"title": "Sec1", "description": "Test."}
             ]}
        ]"""
        chapter = """{
            "sections": [
                {"title": "Sec1", "paragraphs": [
                    {"kind": "body", "sentences": ["Original text."]}
                ]}
            ]
        }"""
        engine.add_response(outline)
        engine.add_response(chapter)
        doc = await writer.generate_outline(uuid4(), uuid4(), "Test", "nonfiction")
        return await writer.generate_chapter(doc, doc.chapters()[0].id)


# ---------------------------------------------------------------------------
# rewrite_sentence
# ---------------------------------------------------------------------------


class TestRewriteSentence:
    SENTENCE_RESPONSE = """{
        "sentences": ["The polished sentence version."]
    }"""

    async def test_rewrites_sentence(
        self, writer: WritingEngine, mock_engine: MockAIEngine
    ) -> None:
        doc = await self._make_doc_with_paragraph(writer, mock_engine)
        mock_engine.add_response(self.SENTENCE_RESPONSE)

        chapter_id = doc.chapters()[0].id
        section_id = doc.sections(chapter_id)[0].id
        para_id = doc.paragraphs(section_id)[0].id
        sent_id = doc.sentences(para_id)[0].id

        doc = await writer.rewrite_sentence(doc, sent_id, "Make it concise")
        rewritten = doc.require(sent_id)
        assert rewritten.text == "The polished sentence version."
        assert rewritten.status == "draft"

    @staticmethod
    async def _make_doc_with_paragraph(
        writer: WritingEngine, engine: MockAIEngine
    ) -> StructuredDocument:
        outline = """[
            {"title": "Ch1", "summary": "X.",
             "sections": [{"title": "Sec1", "description": "Y."}]}
        ]"""
        chapter = """{
            "sections": [{"title": "Sec1", "paragraphs": [
                {"kind": "body", "sentences": ["Original sentence."]}
            ]}]
        }"""
        engine.add_response(outline)
        engine.add_response(chapter)
        doc = await writer.generate_outline(uuid4(), uuid4(), "Test", "nonfiction")
        return await writer.generate_chapter(doc, doc.chapters()[0].id)


# ---------------------------------------------------------------------------
# error cases
# ---------------------------------------------------------------------------


class TestWritingEngineErrors:
    async def test_generate_chapter_wrong_type(self, writer: WritingEngine) -> None:
        doc = StructuredDocument.new_book(uuid4(), uuid4(), "Test")
        sec = node("section")
        ch = node("chapter")
        ch.add_child(sec)
        doc.root.add_child(ch)
        with pytest.raises(ValueError, match="not a chapter"):
            await writer.generate_chapter(doc, sec.id)

    async def test_generate_section_wrong_type(self, writer: WritingEngine) -> None:
        doc = StructuredDocument.new_book(uuid4(), uuid4(), "Test")
        ch = node("chapter")
        doc.root.add_child(ch)
        with pytest.raises(ValueError, match="not a section"):
            await writer.generate_section(doc, ch.id)

    async def test_rewrite_paragraph_wrong_type(self, writer: WritingEngine) -> None:
        doc = StructuredDocument.new_book(uuid4(), uuid4(), "Test")
        ch = node("chapter")
        sec = node("section")
        para = node("paragraph")
        sent = node("sentence", text="test")
        para.add_child(sent)
        sec.add_child(para)
        ch.add_child(sec)
        doc.root.add_child(ch)
        with pytest.raises(ValueError, match="not a paragraph"):
            await writer.rewrite_paragraph(doc, sent.id, "fix")

    async def test_rewrite_sentence_wrong_type(self, writer: WritingEngine) -> None:
        doc = StructuredDocument.new_book(uuid4(), uuid4(), "Test")
        ch = node("chapter")
        doc.root.add_child(ch)
        with pytest.raises(ValueError, match="not a sentence"):
            await writer.rewrite_sentence(doc, ch.id, "fix")
