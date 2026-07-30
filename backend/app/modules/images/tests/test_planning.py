"""Unit tests for image planning heuristics."""

from uuid import uuid4

from app.modules.images.planning.analyzer import analyze_document
from services.document_model import StructuredDocument, node


def build_document() -> StructuredDocument:
    project_id = uuid4()
    book_id = uuid4()
    doc = StructuredDocument.new_book(project_id, book_id, "Visual Book")
    chapter = node("chapter", title="Chapter One")
    section_one = node("section", title="How the process works")
    paragraph_one = node("paragraph")
    paragraph_one.add_child(
        node("sentence", text="This step by step process benefits from a diagram and example.")
    )
    section_one.add_child(paragraph_one)
    chapter.add_child(section_one)

    section_two = node("section", title="A dramatic scene")
    paragraph_two = node("paragraph")
    paragraph_two.add_child(
        node("sentence", text="The setting and character conflict make this scene highly visual.")
    )
    section_two.add_child(paragraph_two)
    chapter.add_child(section_two)

    doc.root.add_child(chapter)
    return doc


def test_analyze_document_returns_ranked_suggestions() -> None:
    doc = build_document()

    analysis = analyze_document(doc, mode="automatic")

    assert len(analysis) == 1
    assert analysis[0].recommended_count >= 1
    assert (
        analysis[0].suggestions[0].importance_score >= analysis[0].suggestions[-1].importance_score
    )


def test_custom_count_distributes_requested_total() -> None:
    doc = build_document()

    analysis = analyze_document(doc, mode="custom", custom_count=1)

    assert sum(item.recommended_count for item in analysis) == 1
