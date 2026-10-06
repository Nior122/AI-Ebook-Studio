# AI Ebook Studio — Prioritized Implementation Roadmap

- **Created:** 2026-10-05
- **Input:** `docs/PROJECT_AUDIT.md`
- **Operating rule:** inspect the existing implementation, preserve working architecture, make a small reversible change, add a regression test, then verify before moving to the next milestone. Do not report a milestone complete on the basis of a route returning 200 or a build passing alone.

## Product goal

Deliver a reliable, user-controlled production workflow: authenticated project → reviewed brief → editable blueprint → focused, resumable manuscript → reversible proofreading/editing → approved image plan and assets → correctly formatted, selectable-layout files → advisory KDP check of the actual export → cover, translation and marketing materials → a validated publishing package.

No step may overwrite an approved/source manuscript without explicit user action. AI suggestions, translations, images, and generated assets must remain attributable and recoverable. Text and image generation must remain provider-independent. **Video generation and video rendering remain out of scope.**

## Global definition of done

A feature is complete only when all applicable items below are satisfied:

1. The main authenticated UI path is wired to the owning backend entity—not a legacy/shell route—and respects per-user access.
2. Success, provider failure, retry, cancellation, partial completion, and reload/resume behavior are defined and tested.
3. Source content remains intact unless the user explicitly confirms replacement. AI rewrites and translations are reviewable and reversible.
4. Persisted output is inspected. For writing: actual text, topic relevance, coverage, repetition, and target length are asserted. For files: the produced DOCX/EPUB/PDF is opened/parsed and dimensions/content/assets are checked.
5. Unit/API tests and a browser-level workflow cover the feature; CI runs the relevant tests. External-provider checks clearly identify when credentials are unavailable.
6. Documentation describes the actual behavior and limitations. Production/deployment claims are withheld until tested against the target service.

## Priority definitions

- **P0 — Protect data and make the core book real:** destructive behavior, misleading manuscript quality/state, identity/configuration errors, unsafe defaults, and tests that conceal them.
- **P1 — Complete the main author workflow:** interactive planning, editing, durable progress, content/image/file integration, and faithful exports.
- **P2 — Finish publishing features:** official-ish advisory checks, covers, marketing, final packaging, broad provider/cost UX, and refinements.
- **P3 — Maintenance / explicit non-goals:** ongoing regression checks and keeping video generation out of scope.

---

## P0 — Data safety and trustworthy generation

### P0.1 — Make translation non-destructive

**Audit evidence:** both `services/translation/engine.py` and the `translation` job handler assign translated strings to source `WritingChapter.content`; current history stores metadata/status but not the translated prose.

**Implementation:** introduce a durable translated edition/output representation linked to source book, source chapter and source revision; keep target language, translation settings, per-chapter state, translated content and errors separate. Route synchronous and asynchronous translation through the same service. Ensure retry replaces only its own target output. Do not silently migrate old overwritten content as if it were recoverable; record that historical originals may already be lost.

**Acceptance criteria:**
- A source manuscript with recorded chapter hashes has identical hashes after successful, failed, cancelled, and retried translations.
- A translated edition can be reopened independently, compared side-by-side, exported, and associated with its source revision/languages.
- Tests cover empty chapters, chunk boundaries, provider failure, partial retry, cross-user book IDs, and both sync and job APIs.
- The UI removes the backup-as-required warning once preservation is guaranteed and shows the destination edition explicitly.

### P0.2 — Repair the generation baseline before adding writing features

**Audit evidence:** no-key API reproduction for a 3,000-word, three-chapter teacher book produced 24,038 words of repetitive generic fallback text, used the phrase “The book” in place of the specified topic, and finished with `needs_review` despite job status `COMPLETED`.

**Implementation:** trace the exact prompt/render/output path end to end. Fix the `LocalProvider` prompt parser and labels, ensure topic/audience/brief/outlines are propagated, and stop treating a missing validation result as a pass. Derive word budgets for sections from the requested manuscript total; bound generation, never pad by repeating boilerplate, and distinguish “job ran” from “manuscript is ready.” Retain the staged pipeline and completed work on failure. If no genuine provider is available, surface the offline/degraded limitation instead of presenting generic content as a finished book.

**Acceptance criteria:**
- The deterministic offline integration test uses a specific topic/audience and cannot produce the generic “The book”/“Foundations” placeholder output.
- A book request within configured supported limits either lands within an agreed tolerance (initial target: 80–120% of the requested main-text count) or ends `needs_review`/failed with a truthful reason; it must not be padded to a false count.
- Actual chapter content is checked for topic anchors, per-chapter objective coverage, duplicate paragraphs, non-empty sections and source/style consistency.
- An unavailable/invalid validator is **unknown**, never `passed`; weak or off-topic content cannot set `ready_for_formatting`.
- The job can finish technically while the manuscript remains visibly `needs_review`; frontend status and next action make that distinction clear.
- Regression tests inspect persisted generated prose, not only chapter count/job termination. A separately marked live-provider quality sample is added when credentials are available.

### P0.3 — Establish one canonical book identity and fix settings/autosave lookup

**Audit evidence:** one logical book is stored in the project-level `Book` and writing-level `WritingBook`; the cross-reference lives in project metadata. Setup writes `BookSettings` against the legacy `Book.id`; export/KDP query with `WritingBook.id`. Autosave can fall back to a user-wide title match.

**Implementation:** use the persisted relationship as the only resolution path. Define which ID each public route accepts; centralize conversion/ownership checks; reject ambiguity rather than silently selecting the first book. Update settings read/write and autosave against the canonical parent. Preserve compatibility for old records through a migration/backfill that reports ambiguous/unlinked records.

**Acceptance criteria:**
- Two projects with the same title for one user have isolated autosave, settings, export, KDP and assets.
- A non-default trim/margin/font setting round-trips setup → database → exported DOCX → KDP report.
- Foreign-user IDs remain inaccessible; every test checks content and owner, not just response codes.
- Old links are backfilled deterministically or surfaced for repair; no heuristic title matching remains.

### P0.4 — Make errors and offline fallback honest

**Implementation:** identify every path that swallows errors, turns unavailable validators into success, or returns a completed cover/job containing an error object. Preserve fallback where useful for safe metadata/planning, but annotate provenance and degrade state; never falsely label the manuscript, cover, or export ready.

**Acceptance criteria:** injected provider errors yield actionable state and retryability; completed assets contain usable content/files; job, book, and UI states agree; no error result is counted as a successful generated asset.

### P0.5 — Production secret validation and authorization tests

**Implementation:** reject known placeholder JWT/encryption secrets and unsafe debug/CORS settings when production mode is enabled. Audit ownership on assets, async handlers, downloads, and restore paths. Keep secrets out of Git and never expose keys back to the client.

**Acceptance criteria:** startup/config tests prove weak defaults fail in production and remain usable in local development; cross-user tests cover each resource family; templates document exact environment variable names for each deployment.

### P0.6 — Restore a green, meaningful quality gate

**Implementation:** update stale frontend tests to the current Clerk route contract rather than restoring obsolete custom-auth pages by default; implement the empty settings suite; align Protected tests with real Clerk state; scope backend lint findings instead of bulk-autofixing; run tests in CI.

**Acceptance criteria:** backend tests, frontend Vitest, typecheck, production build, scoped lint, and migration tests run in CI. A test fails if a content-quality contract regresses. CI checks tests rather than only folder existence.

**P0 exit gate:** translation never mutates its source; actual generated text is evaluated and state is honest; ambiguous IDs/settings are eliminated; unsafe production secrets fail closed; the CI suite is meaningful and green.

---

## P1 — Complete the authoring and production workflow

### P1.1 — Make brief and blueprint reviewable before prose generation

Expose a staged wizard: describe the idea → generate/edit the book brief → approve → generate/edit blueprint/outlines → approve → generate selected chapters or full manuscript. Reuse current specification/blueprint/chapter APIs. Add per-chapter objectives, sections, examples/exercises, reorder/add/remove, regeneration, and “resume from here.” Persist approvals and the exact prompt context/revision used by each generation job.

**Acceptance:** browser test edits and approves brief/blueprint, restarts/refreshes, and continues without silently changing earlier approved material.

### P1.2 — Finish safe editing, proofreading, and version history UX

Replace direct whole-chapter AI mutation with a preview/diff and explicit accept/reject. Wire suggestion actions, filters, severity and chapter-level review counts into the existing workspace. Create a version before accepted whole-chapter edits and expose restore/compare. Add conflict detection to autosave and clear save/error state.

**Acceptance:** no generated suggestion changes content until accepted; acceptance creates recoverable version; reject/undo/restore work after reload; test simultaneous edit/save conflict handling.

### P1.3 — Make background work durable and restart-safe

Choose the durable worker compatible with the production environment. Prefer a transactional database-backed claim/lease using the existing jobs table if Postgres/Neon is the target; otherwise select and document an actual durable broker rather than relying on the unused local Redis container. Commit the queued record before acknowledging submission. Persist stage/section checkpoints and idempotency keys.

**Acceptance:** killing the API during a job does not lose accepted work; one worker claims each job; retry resumes from the last committed checkpoint; cancellation does not corrupt current chapters; progress is available after process restart and from another API instance.

### P1.4 — Use one manuscript representation for writing, images and exports

Create a canonical document structure (or a lossless Markdown-to-document parser) for headings, paragraphs, lists, tables, emphasis, links, captions and images. Bridge existing `WritingChapter` content into it incrementally; do not rewrite the database wholesale. Image plans target stable nodes in an approved revision. Renderers consume the same structure.

**Acceptance:** round-trip tests preserve supported structures and stable IDs; accepted image placements survive edits/restore/reload and export at the correct location; parser rejects/flags unsupported constructs instead of silently dropping them.

### P1.5 — Implement manuscript-aware image planning and review

Analyze every approved chapter/section; propose contextual image descriptions, style/density and placements; let user edit/reorder/skip/approve the plan. Generate only approved prompts, persist bytes/metadata/provider/version, and support retry/regeneration without losing selected alternatives. Keep provider interface-based and credentials server-side.

**Acceptance:** the generated plan references real chapter nodes; plan approval is reversible; images from a mocked provider insert at the right export location; unavailable provider does not erase plan/assets.

### P1.6 — Complete DOCX/EPUB/PDF and selectable trim-size fidelity

Resolve the settings key defect first. Add proper list/table/inline-format/image rendering; include title/author/copyright/TOC/page breaks where supported; implement explicit 6×9 and custom layout; scale figures to usable width while preserving aspect ratio. Add an export preview/metadata check and retain final binaries for inspection.

**Acceptance:** tests open produced DOCX with python-docx/OOXML and verify section dimensions, margins, styles, list/table/image relationships, title and chapter order; EPUB package is inspected; PDF rendered page count/text is checked. 6×9 and one alternate trim size pass from saved user settings.

### P1.7 — Surface persisted progress, approval, assets and book status in the dashboard

Show actual manuscript word count/target, chapter state, last activity, job state/degraded warnings, review needed, assets and resume actions. Use API data only. Retain search, project lifecycle actions and accessible responsive layout.

**Acceptance:** dashboard accurately reflects partial, failed, needs-review, completed, archived and restored projects after reload; no inferred/fake progress.

### P1.8 — Browser-level workflow baseline

Add Playwright (or an existing chosen browser runner), deterministic seeded user/provider, and test helpers. Cover sign-up/sign-in using the configured test auth strategy, book setup, stage review, generation progress/resume, editing/version, proofreading action, translation preservation, image plan/approval, 6×9 export and download, KDP warnings, cover/marketing assets and project ownership.

**Acceptance:** CI runs the browser flow against a fresh test DB; the suite records artifact/screenshots on failure; external AI is mocked in ordinary CI and an opt-in live-provider quality run is clearly separated.

---

## P2 — Finish the publishing features

### P2.1 — KDP advisory checks against the actual export

Parse the exact exported DOCX/PDF and verify trim, margins, document metadata, heading/navigation, blank/near-empty pages, overflow/layout, image resolution/aspect ratio, font embedding/support and chapter order. Explain that readiness is an advisory check, not an official Amazon guarantee; report per-check evidence, severity and repair action. Preserve warnings and let user re-run after changes.

### P2.2 — Real cover generation and editable covers

Generate front/back/spine artwork through the provider abstraction, based on final trim, page count, bleed and paper choice. Use a safe title/subtitle/author overlay layout with editable text and preview; store each version and provide final download. A text brief may remain an optional planning stage, not the output called a generated cover.

### P2.3 — Editable, manuscript-grounded marketing kit

Generate short/long store descriptions, subtitle options, categories/keywords, audience hooks, social copy, launch email, ad copy and short-form content ideas from approved content. Let users edit/save/reopen each result; clearly label AI suggestions and prohibit invented endorsements, sales figures, citations or guarantees.

### P2.4 — Complete file library and final package

Show covers, images, translated editions, interior formats, KDP reports and marketing assets with source revision, created date, provider and file type. Add lifecycle/cleanup controls and a validated package manifest; package only assets the user explicitly approves.

### P2.5 — Provider choice, usage and performance controls

Add per-task provider/model preferences, safe credential health checks, model capabilities, cost/latency/usage estimates, concurrency/rate limits, cancellation and clear user-facing disclosure when a request uses offline fallback. Keep image and text providers independent and swappable.

### P2.6 — UX and accessibility polish

Add inline progress, disabled/loading/error states, accessible keyboard/focus paths, mobile workspace behavior, descriptive tooltips and help. Remove placeholder controls that do not perform an action; favor compact contextual panels over a giant undifferentiated settings screen.

---

## P3 — Ongoing verification and explicit boundaries

- Keep video generation/rendering out of routes, jobs, UI and dependencies unless scope is explicitly changed.
- Re-run security/dependency advisory review before releases; upgrade dependencies in scoped batches with full tests.
- Track project-specific lint debt rather than bulk-rewriting unrelated legacy/test/patch-script files.
- Maintain migrations from real prior schemas and test production database semantics; SQLite success alone is not a PostgreSQL deployment test.
- Update `docs/PROJECT_AUDIT.md` and create/update `docs/FINAL_PRODUCT_AUDIT.md` only after executing the stated acceptance gates. Record unavailable secrets, paid providers, browser infrastructure and deployment checks explicitly.

## Immediate execution order

1. P0.1 non-destructive translation and source-preservation regression tests.
2. P0.2 reproduce and repair actual local-fallback prompt parsing, length behavior, validation semantics and manuscript status; add content-level API integration assertions.
3. P0.3 canonical book identity, autosave and formatting-settings key repair.
4. P0.4–P0.6 production config, stale frontend tests and continuous quality gates.
5. P1 stages in dependency order; do not build image/export features against a second, disconnected manuscript model.

**Roadmap status at creation:** all milestones were planned and none was declared complete. See the dated execution update below; the gates remain open until their acceptance criteria are met.

## Execution update — 2026-10-05

Work has started on P0.1, P0.2, P0.3, P0.4, P0.5, and P0.6. These are **in progress**, not complete.

| Milestone | Current implementation and measured verification | Remaining acceptance work |
|---|---|---|
| **P0.1 — non-destructive translation** | Added separate translated-edition/chapter persistence and an Alembic revision; synchronous and background translation share the safe engine; retry resumes target chapters and rejects changed source content. Backend tests cover successful API translation, source preservation, cross-user access, partial failure/resume, source drift, and the job handler. A fresh SQLite Alembic upgrade reaches the new revision. The studio panel now lists/reopens editions, supports retry, and does not apply translated content to the source editor. Three targeted UI tests pass. | Exercise the migration from a populated production-like PostgreSQL schema; add cancellation behavior and translated-edition export/side-by-side review; complete an authenticated browser workflow. Do not recover historical source text that may already have been overwritten. |
| **P0.2 — trustworthy generation** | Fixed the LocalProvider prompt parsing/dispatch and topic propagation; added bounded section word budgets and strict unknown/incomplete validation handling. Persisted workflow regression now yields **2,854 words for a 3,000-word request** (95.1%, within the current 80–120% gate) and leaves offline content in review rather than publication-ready. Focused generation/translation/production regressions pass. | Continue evaluating the persisted prose for objective coverage, repetition, and topic quality across representative briefs; test configured live providers when credentials are available; retain a clear offline/degraded disclosure. A passing length test is not semantic proof. |
| **P0.3 — canonical identity and settings** | Added nullable, unique `WritingBook.project_book_id` FK, backfilled only unambiguous legacy metadata, and replaced title/order guesses in autosave, generation resume, and job/project resolution with the persisted relationship. Export, KDP and marketing records now write/query `Book.id`; job persistence resolves either supported input ID before saving its FK. Asset retrieval also checks that the writing-book route matches the asset's owner. Response `book_id` is explicitly documented as canonical project `Book.id`, while route paths continue accepting `WritingBook.id`. A conservative data migration repairs unambiguous old SQLite asset/job IDs and leaves ambiguous/unlinked/colliding rows untouched. A duplicate-title autosave test passes. The full production workflow regression enables SQLite foreign keys, proves linked IDs are distinct, checks persisted job/KDP/marketing/export IDs, retrieves a KDP report, downloads DOCX, and rejects a mismatched book path; it also sets 8×10/1.25-inch margins and inspects the DOCX. Migration tests cover unique-vs-ambiguous link backfill and the data repair. | Validate the migration against populated PostgreSQL; provide operator reporting/repair for ambiguous or collision-skipped legacy rows; complete adversarial ownership checks for every asset family. No pre-existing application database file was present in this checkout, so no user SQLite data was available for direct repair inspection. The KDP engine still checks manuscript/settings rather than parsing the exact export; broad 6×9/custom-size regression coverage remains. |
| **P0.4 — honest failures and fallback state** | Removed catch-and-continue behavior from async cover generation: provider failures now reach the runner and mark the job `FAILED`, rather than returning `{error: ...}` as a completed result. Unknown cover components are rejected by the API schema/handler. Restore-point creation exceptions now propagate instead of logging and allowing the job to report `COMPLETED` without its promised recovery point. Regression tests inject both cover-provider and restore-store failures; the full workflow still verifies successful cover-job completion and its restore point. | Continue auditing other operations for swallowed provider failures, empty-but-successful output and degraded/fallback provenance; cover jobs still produce design briefs rather than actual cover image assets. |
| **P0.5 — production configuration** | `Settings` now fails startup in `production`/`prod` for placeholder, short, low-diversity, or reused `SECRET_KEY`/`JWT_SECRET` values; it also rejects `DEBUG=true`, wildcard CORS and non-HTTPS production origins. Pydantic validation errors hide input values so rejected secrets are not echoed. Both environment templates explain the production contract and JWT-key rotation impact. `render.yaml` now allows only the HTTPS Cloudflare Pages origin; a config regression parses the blueprint and validates it against the settings rules. Seven direct valid/invalid config cases plus the blueprint check pass. | Verify Render-generated secret length/format and production startup from the actual deployment; review ownership checks across every asset/job/download resource family. Secrets and deployed service state are not available in this checkout. |
| **P0.6 — meaningful quality gate** | Updated stale sign-in/sign-up component tests to the current Clerk routes, aligned `Protected` tests to Clerk's actual loading/sign-in contract, added settings persistence tests, and added translation-panel interactions. Frontend Vitest **4.1.11** passes **14 tests across 6 files**; Vite is **6.4.3**; clean `npm ci`, typecheck, and `npm run lint` pass (with existing warnings); `npm run build:next` succeeds. The lockfile was refreshed with semver-compatible security fixes. The full backend suite now passes **201 tests**. Production QA enables SQLite FK enforcement for its persistent database fixture. Test `AsyncClient` fixtures use a unique `X-Forwarded-For` address per client, stable for that client's requests, preventing unrelated tests from sharing the in-process auth rate-limit bucket. A fresh SQLite database upgrades through all **19 Alembic revisions** to `20261005_0003`. Focused Ruff checks pass across touched backend code, schemas, migrations and regression tests. `.github/workflows/ci.yml` now runs backend scoped lint/migrations/tests and frontend tests/typecheck/lint/build on PRs and main/master pushes. | GitHub Actions has not run for these unpushed changes; no browser runner or configured Clerk test session exists. Triage existing lint/build warnings and add browser-level workflow coverage before closing P0.6. |

### Next execution order

1. Finish P0.1 edge cases and PostgreSQL migration validation, then add authenticated browser verification when test auth infrastructure is available.
2. Continue P0.2 quality evaluation beyond length (objectives, topic anchors, duplicate/repeated passages, partial-failure recovery).
3. Continue P0.3 by validating the migration on populated PostgreSQL and exposing ambiguous/collision-skipped legacy rows for operator repair; keep the verified asset mapping stable before expanding image or KDP behavior.
4. Proceed through P0.4–P0.6 production configuration and CI integration; do not mark gates closed on unit tests alone.
5. Advance P1 in dependency order; keep DOCX/EPUB/PDF work on a single manuscript representation.

## Deployment-readiness execution update — 2026-10-06

The requested GitHub push and draft PR are in place. GitHub Actions run `37404838248` passed for the pushed `0ae1573` snapshot, but its Cloudflare Workers Builds check failed. The account-only Dashboard logs could not be accessed from the checkout, so the failure was reproduced with the repository's configured build command instead of requesting or using external credentials.

That local reproduction exposed a recursive OpenNext build: the adapter's default Next.js command was `npm run build`, which called the OpenNext build again. The frontend OpenNext configuration now selects `npm run build:next`; the standalone trace root is aligned with OpenNext's expected package-local output. CI now exercises `npm run build` (the actual Cloudflare Worker artifact), not just `next build`. A clean `npm ci`, the 14 frontend tests, typecheck, lint, full OpenNext build, and `wrangler deploy --dry-run` all pass locally. The transitive critical `proxy-addr` advisory was also fixed through a non-breaking lockfile update; `npm audit` now reports **12 advisories (4 moderate, 8 high, 0 critical)**.

**Current gate:** push this fix, then verify the new GitHub Actions and Workers Builds results before any deployment-readiness statement. Local dry-run does not upload a Worker or verify Render, PostgreSQL, production secrets, browser auth, or external AI providers. Keep those acceptance gates open. After remote checks, return to P0.1 translation cancellation/export/side-by-side and populated PostgreSQL validation, then resume the existing P0/P1 order.