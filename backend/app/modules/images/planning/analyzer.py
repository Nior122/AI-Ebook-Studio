"""Structured-manuscript image planning heuristics."""

from __future__ import annotations

from dataclasses import dataclass
from math import ceil
from uuid import UUID

from services.document_model import DocumentNode, DocumentNodeType, StructuredDocument

IMAGE_COUNT_MODES = {"automatic", "low", "medium", "high", "custom"}
ASPECT_RATIOS = {"16:9", "1:1", "9:16", "4:3", "3:2"}
IMAGE_STYLES = {
    "Photorealistic",
    "Digital Painting",
    "Watercolor",
    "Sketch",
    "Flat Illustration",
    "Comic",
    "Fantasy",
    "Cyberpunk",
    "Oil Painting",
    "3D Render",
    "Pixar Style",
    "Anime",
}

_EDUCATIONAL_HINTS = {"diagram", "step", "example", "process", "framework", "compare", "how"}
_NARRATIVE_HINTS = {"scene", "journey", "story", "character", "moment", "setting", "conflict"}
_VISUAL_HINTS = {"visual", "illustration", "image", "map", "layout", "design", "before", "after"}


@dataclass(frozen=True)
class ImageSuggestion:
    """A suggested image placement with planning metadata."""

    chapter_id: UUID
    chapter_title: str
    section_id: UUID
    section_title: str
    paragraph_id: UUID
    paragraph_preview: str
    subject: str
    rationale: str
    importance_score: float
    visual_complexity_score: float
    educational_value_score: float
    narrative_value_score: float
    recommended_order: int


@dataclass(frozen=True)
class ChapterImageAnalysis:
    """Per-chapter analysis summary."""

    chapter_id: UUID
    chapter_title: str
    recommended_count: int
    suggestions: list[ImageSuggestion]


def analyze_document(
    doc: StructuredDocument,
    *,
    mode: str = "automatic",
    custom_count: int | None = None,
) -> list[ChapterImageAnalysis]:
    """Analyze a structured document and return chapter-level image suggestions."""
    resolved_mode = mode if mode in IMAGE_COUNT_MODES else "automatic"
    chapters = doc.chapters()
    chapter_summaries: list[ChapterImageAnalysis] = []

    all_candidates: list[tuple[DocumentNode, list[ImageSuggestion]]] = []
    for chapter in chapters:
        suggestions = _chapter_candidates(chapter)
        all_candidates.append((chapter, suggestions))

    if resolved_mode == "custom" and custom_count is not None:
        selected_by_chapter = _distribute_custom_count(all_candidates, max(0, custom_count))
    else:
        selected_by_chapter = {
            chapter.id: _pick_count(chapter, suggestions, resolved_mode)
            for chapter, suggestions in all_candidates
        }

    for chapter, suggestions in all_candidates:
        count = selected_by_chapter.get(chapter.id, 0)
        chosen = suggestions[:count]
        chapter_summaries.append(
            ChapterImageAnalysis(
                chapter_id=chapter.id,
                chapter_title=chapter.title or "Untitled Chapter",
                recommended_count=count,
                suggestions=chosen,
            )
        )

    return chapter_summaries


def _chapter_candidates(chapter: DocumentNode) -> list[ImageSuggestion]:
    chapter_title = chapter.title or "Untitled Chapter"
    suggestions: list[ImageSuggestion] = []
    for section_order, section in enumerate(chapter.children):
        if section.node_type != DocumentNodeType.SECTION:
            continue
        paragraph = next(
            (child for child in section.children if child.node_type == DocumentNodeType.PARAGRAPH),
            None,
        )
        if paragraph is None:
            continue
        preview = _paragraph_preview(paragraph)
        if not preview:
            continue
        educational = _keyword_score(preview, _EDUCATIONAL_HINTS)
        narrative = _keyword_score(preview, _NARRATIVE_HINTS)
        visual = _keyword_score(preview, _VISUAL_HINTS | _EDUCATIONAL_HINTS | _NARRATIVE_HINTS)
        complexity = min(1.0, (len(preview.split()) / 80.0) + (0.15 if section.title else 0.0))
        importance = min(1.0, (0.35 * educational) + (0.25 * narrative) + (0.40 * visual))
        subject = section.title or chapter_title
        suggestions.append(
            ImageSuggestion(
                chapter_id=chapter.id,
                chapter_title=chapter_title,
                section_id=section.id,
                section_title=section.title or "Untitled Section",
                paragraph_id=paragraph.id,
                paragraph_preview=preview[:240],
                subject=subject,
                rationale=_rationale(educational, narrative, visual),
                importance_score=round(max(importance, 0.25 + complexity / 4), 3),
                visual_complexity_score=round(complexity, 3),
                educational_value_score=round(educational, 3),
                narrative_value_score=round(narrative, 3),
                recommended_order=section_order + 1,
            )
        )
    suggestions.sort(
        key=lambda item: (
            item.importance_score,
            item.visual_complexity_score,
            item.educational_value_score,
            item.narrative_value_score,
        ),
        reverse=True,
    )
    return suggestions


def _pick_count(chapter: DocumentNode, suggestions: list[ImageSuggestion], mode: str) -> int:
    if not suggestions:
        return 0
    section_count = sum(
        1 for child in chapter.children if child.node_type == DocumentNodeType.SECTION
    )
    base_count = max(1, ceil(section_count / 2))
    multiplier = {
        "automatic": 1.0,
        "low": 0.6,
        "medium": 1.0,
        "high": 1.5,
    }.get(mode, 1.0)
    boosted = ceil(base_count * multiplier)
    return min(len(suggestions), max(1, boosted))


def _distribute_custom_count(
    chapter_candidates: list[tuple[DocumentNode, list[ImageSuggestion]]],
    custom_count: int,
) -> dict[UUID, int]:
    ranked: list[tuple[UUID, float]] = []
    for chapter, suggestions in chapter_candidates:
        ranked.extend((chapter.id, suggestion.importance_score) for suggestion in suggestions)
    ranked.sort(key=lambda item: item[1], reverse=True)
    chosen = ranked[:custom_count]
    result: dict[UUID, int] = {}
    for chapter_id, _score in chosen:
        result[chapter_id] = result.get(chapter_id, 0) + 1
    return result


def _paragraph_preview(paragraph: DocumentNode) -> str:
    parts = [
        child.text for child in paragraph.children if child.node_type == DocumentNodeType.SENTENCE
    ]
    return " ".join(part for part in parts if part).strip()


def _keyword_score(text: str, keywords: set[str]) -> float:
    lowered = text.lower()
    score = sum(1 for keyword in keywords if keyword in lowered)
    return min(1.0, score / 3)


def _rationale(educational: float, narrative: float, visual: float) -> str:
    if educational >= narrative and educational >= visual:
        return (
            "High educational value and explanatory density make this passage "
            "a strong image target."
        )
    if narrative >= educational and narrative >= visual:
        return (
            "Narrative beats and scene-setting suggest a supporting "
            "illustration would add clarity."
        )
    return "The section contains visually rich concepts that benefit from " "explicit illustration."
