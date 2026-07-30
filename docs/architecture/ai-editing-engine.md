# Phase 7 — AI Manuscript Editing & Proofreading Engine

## Overview

The AI Editing Engine transforms draft manuscripts into reviewed, approved manuscripts through a structured, reviewable suggestion system. It preserves the author's original content — AI never silently replaces text. Every proposed change must be explicitly accepted or rejected by the user.

## Architecture

```
User → Book → Chapter → ChapterVersion (Phase 6)
                        ↕
                EditingSession → SuggestionBatch → EditingSuggestion
                                                    ↕
                                              ReviewJob (batch)
```

All AI calls go through the provider-agnostic `AIService` (Phase 5). No provider SDK is imported in the editing engine.

## Editing Pipeline

```
DRAFT → AI Analysis → Grammar → Spelling → Clarity → Style
  → Consistency → Repetition → Structure → User Review → Accept/Reject → APPROVED
```

Each stage produces structured suggestions stored in the database. The user reviews each suggestion individually or in bulk.

## Editing Modes

| Mode | Checks |
|------|--------|
| `proofreading` | Spelling, grammar, punctuation, capitalization, word usage |
| `clarity_editing` | Confusing sentences, vague wording, unnecessary complexity |
| `style_editing` | Inconsistent tone, unnatural writing, weak transitions, filler |
| `structural_editing` | Chapter flow, section order, missing explanations |
| `consistency_check` | Terminology, names, capitalization, abbreviations, tone |
| `repetition_check` | Repeated ideas, examples, phrases (flagged, never auto-deleted) |
| `full_review` | All of the above in one pass |
| `fact_check` | Potential facts requiring verification (never claims external verification) |

## Suggestion Model

Each suggestion contains:

- `id` — stable UUID
- `chapter_id` — owning chapter
- `session_id` — editing session that created it
- `category` — grammar, spelling, punctuation, clarity, style, tone, structure, consistency, repetition, fact_check
- `severity` — low, medium, high
- `confidence` — 0.0 to 1.0
- `original_text` — verbatim excerpt from the manuscript
- `suggested_text` — corrected/rewritten version (or null for advisory suggestions)
- `explanation` — why the change is recommended
- `location_data` — `{start, end, anchor}` for UI highlighting
- `status` — pending, accepted, rejected, ignored
- `accepted_at` / `rejected_at` / `ignored_at` — timestamps

## Version Control

Every accepted suggestion (or bulk accept-all) creates a new `ChapterVersion` (append-only):

```
Version 1: Original Draft
Version 2: After AI Proofreading (accepted suggestions applied)
Version 3: After Clarity Editing
Version 4: User Approved
```

Versions are never overwritten. The user can restore any previous version (which itself creates a new version snapshot).

## Review Jobs (Batch Processing)

For full-manuscript reviews, a `ReviewJob` processes chapters one at a time:

```
ReviewJob created (queued)
  → Process Chapter 1 (processing → saving_suggestions)
  → Process Chapter 2
  → ...
  → Completed
```

The job stores `progress_data` — a per-chapter status array so the UI can show live progress. Users can leave the page and poll the job status later. If a chapter fails, the job is marked `failed` with an error message, and existing content is preserved.

## API Endpoints

All mounted under `/api/v1/editing`:

| Method | Path | Description |
|--------|------|-------------|
| POST | `/chapters/{chapter_id}/review` | Run AI review on a chapter |
| POST | `/chapters/{chapter_id}/review-selection` | Quick action on selected text |
| GET | `/chapters/{chapter_id}/suggestions` | List suggestions (filterable) |
| POST | `/chapters/{chapter_id}/suggestions/accept-all` | Accept all pending |
| POST | `/chapters/{chapter_id}/suggestions/reject-all` | Reject all pending |
| GET | `/chapters/{chapter_id}/review-summary` | Aggregate stats |
| GET | `/suggestions/{suggestion_id}` | Get single suggestion |
| POST | `/suggestions/{suggestion_id}/accept` | Accept (applies to manuscript) |
| POST | `/suggestions/{suggestion_id}/reject` | Reject (manuscript unchanged) |
| POST | `/suggestions/{suggestion_id}/ignore` | Ignore (hide) |
| POST | `/suggestions/{suggestion_id}/regenerate` | Regenerate (old → ignored, new → pending) |
| POST | `/books/{book_id}/review-job/start` | Start full-manuscript review job |
| POST | `/review-jobs/{job_id}/process` | Process next chapter in job |
| GET | `/review-jobs/{job_id}` | Get job status |
| GET | `/books/{book_id}/review-jobs` | List jobs for a book |
| POST | `/diff` | Compute textual diff |

## Content Safety

1. **AI never silently replaces manuscript text.** Suggestions are stored as proposed changes.
2. **Accepting a suggestion** applies the `suggested_text` to the chapter and creates a new `ChapterVersion`.
3. **Rejecting or ignoring** leaves the chapter untouched.
4. **AI failure** (provider down, timeout, malformed response) raises `ServiceUnavailableError` (503) with message "AI editing failed. Your existing manuscript content was not changed."
5. **Fact checking** never claims external verification. Suggestions use "Potential fact requiring verification."

## Ownership Security (IDOR Protection)

Every endpoint transitively verifies ownership:

```
Suggestion → Chapter → Book → User
```

- `_get_suggestion()` loads the suggestion, then calls `_get_chapter()` which calls `_get_book()` which checks `book.user_id == user.id`.
- User A cannot read, accept, reject, or modify User B's suggestions.
- Tested in `tests/test_editing.py::test_user_b_cannot_list` and `test_user_b_cannot_accept`.

## Diff System

`services/editing/diff.py` uses `difflib.SequenceMatcher` to produce segment-style diffs:

```json
[
  {"type": "same", "text": "AI tools "},
  {"type": "removed", "text": "is"},
  {"type": "added", "text": "are"},
  {"type": "same", "text": " becoming useful."}
]
```

The frontend renders these as colored spans (red strikethrough for removed, green for added).

## Error Handling

| Error | HTTP | Behavior |
|-------|------|----------|
| `AIProviderError` | 503 | Content preserved, job marked failed |
| Malformed AI output | 503 | Empty suggestions list returned, content preserved |
| Suggestion not found / wrong owner | 404 | `ResourceNotFoundError` |
| Accept already-accepted suggestion | 409 | `ConflictError` |

## Database Tables

| Table | Purpose |
|-------|---------|
| `ed_sessions` | One editing pass per chapter (mode, status) |
| `ed_batches` | Groups suggestions from one AI call |
| `ed_suggestions` | Individual AI-proposed changes |
| `ed_review_jobs` | Batch review across multiple chapters |

## Files

- `models/editing.py` — 4 models
- `schemas/editing.py` — Pydantic schemas
- `services/editing/context.py` — Review context builder
- `services/editing/prompts.py` — System/user prompt templates
- `services/editing/engine.py` — EditingEngine (uses AIService)
- `services/editing/service.py` — CRUD + accept/reject + versioning + ownership
- `services/editing/diff.py` — Diff utility
- `api/v1/editing.py` — 16 API routes
- `tests/test_editing.py` — 20 tests
- `frontend/lib/api/editing.ts` — Frontend API client
- `frontend/types/api.ts` — Phase 7 TypeScript types
