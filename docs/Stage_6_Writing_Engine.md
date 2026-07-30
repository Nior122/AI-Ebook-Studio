# Stage 6 Writing Engine

## Purpose

Stage 6 establishes the Writing Engine as a structured-manuscript system, not a plain-text generator.

The canonical hierarchy is:

`Project -> Book -> Part (optional) -> Chapter -> Section -> Paragraph -> Sentence`

Every node has a stable unique identifier. Future modules must read and mutate this structure directly.

## Architectural Rule

The Writing Engine must call `AIEngine.generate()` and never talk to providers directly.

The Writing Engine must return `DocumentNode` trees and `StructuredDocument` instances.

Plain text is allowed only as a derived representation for:

- Prompt context
- Preview rendering
- Search indexing
- Export pipelines

## Why This Matters

This structure avoids reparsing long chapter strings every time the product needs to:

- Rewrite one paragraph
- Attach an image plan to one section
- Translate one chapter
- Run validation on a subsection
- Export deterministic DOCX or KDP-ready layouts

## Persistence Model

The normalized database source of truth is:

- `books`
- `document_parts`
- `document_chapters`
- `document_sections`
- `document_paragraphs`
- `document_sentences`

`books` stores container metadata. Prose itself is stored in sentence nodes with paragraph, section, chapter, and optional part relationships.

## Module Contract

Future modules should target node ids instead of raw text blobs.

Examples:

- Editing: revise `paragraph_id`
- Images: attach plan to `section_id`
- Translation: localize `chapter_id` or `sentence_id`
- Validation: flag `section_id` or `sentence_id`
- Export: traverse the full document tree in order

## API Direction

Future Writing and Editing APIs should prefer payloads such as:

```json
{
  "target_node_id": "para_123",
  "instruction": "Make this more concise",
  "provider": "openai"
}
```

Responses should return changed node ids or structured subtrees rather than only flattened prose.

## Current Foundation

The backend already includes:

- Structured document domain model
- Normalized persistence tables and migration
- Writing Engine generation and persistence bridge
- Tests covering tree traversal, serialization, and writing flows

This keeps Stage 6 aligned with later Editing, Images, Translation, Validation, and Export stages from day one.
