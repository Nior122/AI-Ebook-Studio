"""Tests for the structured document model (services.document_model)."""

from uuid import UUID, uuid4

import pytest

from services.document_model import (
    DocumentModelError,
    DocumentNode,
    DocumentNodeType,
    StructuredDocument,
    node,
)


class TestDocumentNode:
    def test_create_node(self) -> None:
        n = node("chapter", title="Chapter 1")
        assert n.node_type == DocumentNodeType.CHAPTER
        assert n.title == "Chapter 1"
        assert isinstance(n.id, UUID)
        assert n.status == "draft"
        assert n.children == []

    def test_add_child_valid_parent(self) -> None:
        book = node("book")
        chapter = node("chapter")
        book.add_child(chapter)
        assert chapter in book.children
        assert chapter.parent_id == book.id
        assert chapter.position == 0

    def test_add_child_invalid_parent(self) -> None:
        # A sentence cannot have children
        sentence = node("sentence")
        with pytest.raises(DocumentModelError):
            sentence.add_child(node("paragraph"))
        # A paragraph cannot contain a chapter
        para = node("paragraph")
        with pytest.raises(DocumentModelError):
            para.add_child(node("chapter"))

    def test_insert_child(self) -> None:
        book = node("book")
        ch1 = node("chapter", title="Ch1")
        ch2 = node("chapter", title="Ch2")
        book.add_child(ch1)
        book.insert_child(0, ch2)
        assert book.children[0].title == "Ch2"
        assert book.children[1].title == "Ch1"
        assert ch2.position == 0
        assert ch1.position == 1

    def test_remove_child_by_node(self) -> None:
        book = node("book")
        ch = node("chapter")
        book.add_child(ch)
        removed = book.remove_child(ch)
        assert removed is ch
        assert ch not in book.children
        assert ch.parent_id is None

    def test_remove_child_by_id(self) -> None:
        book = node("book")
        ch = node("chapter")
        book.add_child(ch)
        removed = book.remove_child(ch.id)
        assert removed is ch

    def test_remove_nonexistent_child(self) -> None:
        book = node("book")
        assert book.remove_child(uuid4()) is None

    def test_replace_child(self) -> None:
        book = node("book")
        old = node("chapter", title="Old")
        book.add_child(old)
        new = node("chapter", title="New")
        returned_old = book.replace_child(old.id, new)
        assert returned_old is old
        assert book.children[0].title == "New"
        assert new.position == 0

    def test_replace_nonexistent_child(self) -> None:
        book = node("book")
        with pytest.raises(DocumentModelError):
            book.replace_child(uuid4(), node("chapter"))

    def test_find(self) -> None:
        book = node("book")
        ch = node("chapter")
        sec = node("section")
        book.add_child(ch)
        ch.add_child(sec)
        assert book.find(sec.id) is sec

    def test_find_self(self) -> None:
        n = node("chapter")
        assert n.find(n.id) is n

    def test_find_missing(self) -> None:
        book = node("book")
        assert book.find(uuid4()) is None

    def test_find_by_type(self) -> None:
        book = node("book")
        ch1 = node("chapter")
        ch2 = node("chapter")
        sec = node("section")
        book.add_child(ch1)
        book.add_child(ch2)
        ch1.add_child(sec)
        chapters = book.find_by_type(DocumentNodeType.CHAPTER)
        assert len(chapters) == 2
        sections = book.find_by_type(DocumentNodeType.SECTION)
        assert len(sections) == 1

    def test_walk(self) -> None:
        book = node("book")
        ch = node("chapter")
        sec = node("section")
        book.add_child(ch)
        ch.add_child(sec)
        ids = [n.id for n in book.walk()]
        assert len(ids) == 3
        assert ids[0] == book.id
        assert ids[1] == ch.id
        assert ids[2] == sec.id

    def test_plain_text_single_sentence(self) -> None:
        p = node("paragraph")
        s = node("sentence", text="Hello world.")
        p.add_child(s)
        assert p.plain_text() == "Hello world."

    def test_plain_text_multiple_sentences(self) -> None:
        p = node("paragraph")
        p.add_child(node("sentence", text="First."))
        p.add_child(node("sentence", text="Second."))
        p.add_child(node("sentence", text="Third."))
        assert p.plain_text() == "First. Second. Third."

    def test_plain_text_section_with_title(self) -> None:
        sec = node("section", title="Overview")
        p1 = node("paragraph")
        p1.add_child(node("sentence", text="Para one."))
        p2 = node("paragraph")
        p2.add_child(node("sentence", text="Para two."))
        sec.add_child(p1)
        sec.add_child(p2)
        text = sec.plain_text()
        assert "Overview" in text
        assert "Para one" in text
        assert "Para two" in text

    def test_word_count(self) -> None:
        p = node("paragraph")
        p.add_child(node("sentence", text="One two three."))
        p.add_child(node("sentence", text="Four five six seven."))
        assert p.word_count() == 7

    def test_set_text_on_leaf(self) -> None:
        s = node("sentence")
        s.set_text("Hello.")
        assert s.text == "Hello."

    def test_set_text_on_branch_with_children_raises(self) -> None:
        p = node("paragraph")
        p.add_child(node("sentence", text="Test."))
        with pytest.raises(DocumentModelError):
            p.set_text("New text")

    def test_attach_detach(self) -> None:
        n = node("section")
        n.attach("image_ref", {"url": "test.png"})
        assert n.attachments["image_ref"]["url"] == "test.png"
        val = n.detach("image_ref")
        assert val is not None
        assert val["url"] == "test.png"
        assert "image_ref" not in n.attachments

    def test_to_dict_roundtrip(self) -> None:
        book = node("book", title="My Book")
        ch = node("chapter", title="Ch1")
        sec = node("section", title="Sec1")
        para = node("paragraph", kind="body")
        para.add_child(node("sentence", text="Hello."))
        sec.add_child(para)
        ch.add_child(sec)
        book.add_child(ch)

        d = book.to_dict()
        restored = DocumentNode.from_dict(d)
        assert restored.title == "My Book"
        assert restored.children[0].title == "Ch1"
        assert restored.children[0].children[0].title == "Sec1"
        assert restored.children[0].children[0].children[0].kind == "body"
        assert restored.children[0].children[0].children[0].children[0].text == "Hello."
        assert restored.id == book.id


class TestStructuredDocument:
    def test_new_book(self) -> None:
        project_id = uuid4()
        book_id = uuid4()
        doc = StructuredDocument.new_book(project_id, book_id, "Test Book")
        assert doc.project_id == project_id
        assert doc.book_id == book_id
        assert doc.root.title == "Test Book"
        assert doc.root.node_type == DocumentNodeType.BOOK
        assert len(doc.chapters()) == 0

    def test_find_and_require(self) -> None:
        doc = self._make_doc()
        ch = doc.root.children[0]
        assert doc.find(ch.id) is ch
        assert doc.require(ch.id) is ch

    def test_require_missing(self) -> None:
        doc = self._make_doc()
        with pytest.raises(DocumentModelError):
            doc.require(uuid4())

    def test_chapters_list(self) -> None:
        doc = self._make_doc()
        chapters = doc.chapters()
        assert len(chapters) == 2

    def test_sections(self) -> None:
        doc = self._make_doc()
        sections = doc.sections(doc.root.children[0].id)
        assert len(sections) == 1

    def test_paragraphs(self) -> None:
        doc = self._make_doc()
        chapter = doc.root.children[0]
        section = chapter.children[0]
        paragraphs = doc.paragraphs(section.id)
        assert len(paragraphs) == 1

    def test_sentences(self) -> None:
        doc = self._make_doc()
        chapter = doc.root.children[0]
        section = chapter.children[0]
        para = section.children[0]
        sentences = doc.sentences(para.id)
        assert len(sentences) == 1
        assert sentences[0].text == "Hello world."

    def test_walk(self) -> None:
        doc = self._make_doc()
        ids = [n.id for n in doc.walk()]
        assert len(ids) == 7  # book + 2 ch + 2 sec + 1 para + 1 sent

    def test_plain_text_book(self) -> None:
        doc = self._make_doc()
        text = doc.plain_text()
        assert "Hello world" in text

    def test_word_count_book(self) -> None:
        doc = self._make_doc()
        assert doc.word_count() == 2  # "Hello world."

    def test_map_leaves(self) -> None:
        doc = self._make_doc()
        doc.map_leaves(lambda n: n.set_text(n.text.upper() if n.text else ""))
        sentences = doc.root.find_by_type(DocumentNodeType.SENTENCE)
        assert all(s.text is not None and s.text == s.text.upper() for s in sentences)

    def test_snapshot_roundtrip(self) -> None:
        doc = self._make_doc()
        snapshot = doc.to_snapshot()
        restored = StructuredDocument.from_snapshot(snapshot)
        assert restored.project_id == doc.project_id
        assert restored.book_id == doc.book_id
        assert restored.root.title == doc.root.title
        assert len(restored.chapters()) == len(doc.chapters())
        # sentence is 4 levels deep: book → chapter → section → paragraph → sentence
        sentence = restored.root.children[0].children[0].children[0].children[0]
        assert sentence.text == "Hello world."

    def test_chapters_under_parts(self) -> None:
        project_id = uuid4()
        book_id = uuid4()
        doc = StructuredDocument.new_book(project_id, book_id, "Partitioned Book")
        part = node("part", title="Part One")
        doc.root.add_child(part)
        ch1 = node("chapter", title="Ch1")
        ch2 = node("chapter", title="Ch2")
        part.add_child(ch1)
        doc.root.add_child(ch2)
        assert len(doc.chapters()) == 2
        assert doc.root.children[0].children[0].title == "Ch1"

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _make_doc() -> StructuredDocument:
        doc = StructuredDocument.new_book(uuid4(), uuid4(), "Test Book")
        ch1 = node("chapter", title="Chapter 1")
        sec1 = node("section", title="Section 1.1")
        para1 = node("paragraph", kind="body")
        para1.add_child(node("sentence", text="Hello world."))
        sec1.add_child(para1)
        ch1.add_child(sec1)
        doc.root.add_child(ch1)

        ch2 = node("chapter", title="Chapter 2")
        sec2 = node("section", title="Section 2.1")
        ch2.add_child(sec2)
        doc.root.add_child(ch2)
        return doc
