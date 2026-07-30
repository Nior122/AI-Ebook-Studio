# Software Development Roadmap

## Purpose

This roadmap defines the complete build sequence for AI Ebook Studio from infrastructure foundation to production deployment.

This is documentation only. It does not implement application code, migrations, UI screens, endpoints, or deployment automation.

## Roadmap Principles

- Build infrastructure and platform foundations before product features.
- Keep every milestone independently reviewable.
- Preserve clean architecture boundaries from the start.
- Use provider abstractions before integrating any AI or image vendor.
- Add tests with each milestone rather than saving quality work for the end.
- Deploy only after security, observability, migrations, and rollback paths are ready.

## Build Order Summary

```text
01 Infrastructure Foundation
02 Repository Quality Gates
03 Backend Application Shell
04 Database And Migration Foundation
05 Frontend Application Shell
06 Authentication And Authorization
07 Project And Book Workspace
08 Writing Module
09 Editing Module
10 Prompt And Provider Infrastructure
11 Image Planning And Generation
12 Formatting Module
13 Validation And KDP Readiness
14 Cover Generator
15 Marketing Module
16 Translation Module
17 Export Module
18 History, Notifications, And Jobs
19 Settings, API Keys, And Admin Foundations
20 Billing And Usage Controls
21 End-To-End QA And Hardening
22 Staging Deployment
23 Production Deployment
```

## Complexity Scale

- Low: localized work with limited risk.
- Medium: multiple modules or user-facing workflows.
- High: cross-cutting architecture, persistence, security, or provider integrations.
- Very High: production deployment, billing, export engines, or multi-step workflows.

## Milestone 01: Infrastructure Foundation

Objective:
Establish the repository, environment conventions, local infrastructure, and deployment targets before application code grows.

Tasks:
- Confirm monorepo structure.
- Finalize environment variable naming.
- Define local PostgreSQL and Redis development setup.
- Document Cloudflare Pages, Render, and Neon responsibilities.
- Define branch strategy and release environments.

Expected files:
- `README.md`
- `.env.example`
- `docker-compose.yml`
- `docs/Deployment.md`
- `docs/Architecture.md`
- `.github/workflows/ci.yml`

Acceptance checklist:
- Required root folders exist.
- Environment template documents all required variables.
- Local data services are documented.
- Deployment targets are clearly assigned.
- No feature code is introduced.

Testing checklist:
- Verify `docker compose config` is valid.
- Verify docs reference correct environment variable names.
- Verify CI workflow syntax is valid.

Git commit recommendation:
- `chore: establish infrastructure foundation`

Risk assessment:
- Risk: unclear environment naming causes future configuration drift.
- Mitigation: centralize variable names in `.env.example` and documentation.

Estimated complexity:
- Medium

Build order:
- First milestone.

## Milestone 02: Repository Quality Gates

Objective:
Add project-wide quality expectations before feature development begins.

Tasks:
- Configure frontend linting, type checking, and build checks.
- Configure backend linting, type checking, and test commands.
- Define pull request quality expectations.
- Add formatting and testing documentation.

Expected files:
- `frontend/package.json`
- `frontend/eslint.config.mjs`
- `frontend/tsconfig.json`
- `backend/pyproject.toml`
- `docs/Coding_Standards.md`
- `docs/Testing_Checklist.md`
- `.github/workflows/ci.yml`

Acceptance checklist:
- Frontend type check command exists.
- Frontend build command exists.
- Backend lint/type/test commands are documented.
- CI has placeholders or active checks for both apps.

Testing checklist:
- Run frontend type check.
- Run frontend build.
- Run backend lint command once backend package exists.
- Run backend tests once test harness exists.

Git commit recommendation:
- `chore: add repository quality gates`

Risk assessment:
- Risk: strict quality gates slow early iteration.
- Mitigation: start with essential gates and expand as modules stabilize.

Estimated complexity:
- Medium

Build order:
- After infrastructure foundation.

## Milestone 03: Backend Application Shell

Objective:
Create the FastAPI application shell without business features.

Tasks:
- Add FastAPI app factory.
- Add API version prefix.
- Add health endpoint.
- Add structured configuration loading.
- Add logging foundation.
- Add CORS configuration.
- Add error response conventions.

Expected files:
- `backend/app/main.py`
- `backend/api/router.py`
- `backend/api/v1/router.py`
- `backend/core/config.py`
- `backend/core/logging.py`
- `backend/core/errors.py`
- `backend/tests/test_health.py`

Acceptance checklist:
- FastAPI app starts locally.
- `/health` or `/api/v1/health` returns expected status.
- OpenAPI schema is generated.
- Error envelope convention is documented and represented.

Testing checklist:
- Run backend unit tests.
- Verify health endpoint with test client.
- Verify CORS settings are loaded from environment.
- Verify app fails clearly when required config is missing.

Git commit recommendation:
- `feat: add backend application shell`

Risk assessment:
- Risk: early app shell may accumulate business logic.
- Mitigation: keep routers thin and feature-free.

Estimated complexity:
- Medium

Build order:
- After quality gates.

## Milestone 04: Database And Migration Foundation

Objective:
Prepare SQLAlchemy and Alembic for future schema work without implementing all product tables at once.

Tasks:
- Configure async SQLAlchemy engine.
- Configure session dependency.
- Initialize Alembic.
- Add base model conventions.
- Add migration review rules.
- Connect to Neon-compatible PostgreSQL.

Expected files:
- `backend/database/session.py`
- `backend/database/base.py`
- `backend/database/dependencies.py`
- `backend/alembic.ini`
- `backend/alembic/env.py`
- `backend/models/base.py`
- `docs/Database_Design.md`

Acceptance checklist:
- App can create database sessions.
- Alembic can detect metadata.
- Migration command is documented.
- No product schema is added beyond required baseline.

Testing checklist:
- Test database session lifecycle.
- Test app startup with valid database URL.
- Verify Alembic config imports metadata.
- Run migration command against local database when baseline exists.

Git commit recommendation:
- `chore: add database and migration foundation`

Risk assessment:
- Risk: async database configuration mistakes can create connection leaks.
- Mitigation: use dependency-managed sessions and explicit engine lifecycle.

Estimated complexity:
- High

Build order:
- After backend app shell.

## Milestone 05: Frontend Application Shell

Objective:
Create the authenticated-app layout foundation without product features.

Tasks:
- Define route groups for public and app areas.
- Add app shell layout.
- Add global top bar, sidebar, and responsive layout components.
- Add theme tokens and dark mode foundation.
- Add API client conventions.
- Add empty-state patterns.

Expected files:
- `frontend/app/(public)/layout.tsx`
- `frontend/app/(app)/layout.tsx`
- `frontend/components/layouts/app-shell.tsx`
- `frontend/components/layouts/sidebar.tsx`
- `frontend/components/layouts/top-bar.tsx`
- `frontend/lib/api.ts`
- `frontend/styles/globals.css`
- `docs/UI_Interface_Blueprint.md`

Acceptance checklist:
- Frontend builds.
- App shell renders with responsive layout.
- Navigation placeholders match product modules.
- No feature workflow is implemented.

Testing checklist:
- Run frontend type check.
- Run frontend build.
- Verify desktop and mobile layout manually or with screenshots.
- Verify dark mode tokens render correctly.

Git commit recommendation:
- `feat: add frontend application shell`

Risk assessment:
- Risk: premature feature UI leaks into shell.
- Mitigation: keep shell generic and route content minimal.

Estimated complexity:
- Medium

Build order:
- After backend and database foundation.

## Milestone 06: Authentication And Authorization

Objective:
Implement secure user identity and protected route boundaries.

Tasks:
- Add user model and auth schemas.
- Add registration, login, refresh, logout, and current-user endpoints.
- Add password hashing.
- Add JWT or session strategy.
- Add frontend auth context.
- Add protected route behavior.
- Add authorization dependency patterns.

Expected files:
- `backend/models/user.py`
- `backend/schemas/auth.py`
- `backend/api/v1/auth.py`
- `backend/services/auth_service.py`
- `backend/core/security.py`
- `frontend/contexts/auth-context.tsx`
- `frontend/services/auth-service.ts`
- `frontend/app/(public)/login/page.tsx`

Acceptance checklist:
- User can register.
- User can log in.
- Protected API routes reject unauthenticated requests.
- Frontend can persist session state securely.
- Passwords are never stored in plain text.

Testing checklist:
- Unit tests for password hashing.
- API tests for auth flows.
- Tests for invalid credentials.
- Tests for protected endpoint access.
- Frontend auth state smoke tests.

Git commit recommendation:
- `feat: implement authentication foundation`

Risk assessment:
- Risk: auth mistakes create security exposure.
- Mitigation: test negative cases and avoid custom cryptography.

Estimated complexity:
- High

Build order:
- After frontend shell.

## Milestone 07: Project And Book Workspace

Objective:
Implement core project, book, and chapter persistence and the first usable workspace.

Tasks:
- Add project, book, and chapter models.
- Add CRUD endpoints.
- Add dashboard and project list.
- Add project detail view.
- Add chapter list and chapter editor base.
- Add ownership authorization.

Expected files:
- `backend/models/project.py`
- `backend/models/book.py`
- `backend/models/chapter.py`
- `backend/api/v1/projects.py`
- `backend/api/v1/books.py`
- `backend/schemas/projects.py`
- `backend/repositories/project_repository.py`
- `frontend/app/(app)/dashboard/page.tsx`
- `frontend/app/(app)/projects/page.tsx`
- `frontend/app/(app)/projects/[projectId]/page.tsx`

Acceptance checklist:
- User can create and view projects.
- User can create books inside projects.
- User can create and update chapters.
- Users cannot access other users’ projects.
- Project status and timestamps update correctly.

Testing checklist:
- API tests for project CRUD.
- API tests for authorization boundaries.
- Repository tests for project/book/chapter persistence.
- Frontend smoke tests for create/open flows.

Git commit recommendation:
- `feat: add project and book workspace`

Risk assessment:
- Risk: incorrect ownership checks expose user content.
- Mitigation: enforce project ownership in repositories/services and test cross-user access.

Estimated complexity:
- High

Build order:
- After authentication.

## Milestone 08: Writing Module

Objective:
Add manuscript writing workflows and writing session tracking.

Tasks:
- Add writing session model.
- Add outline and draft generation endpoints.
- Add chapter writing workspace.
- Add AI job handoff without locking UI.
- Add accept/apply generated output flow.
- Add writing history records.

Expected files:
- `backend/models/writing_session.py`
- `backend/api/v1/writing.py`
- `backend/schemas/writing.py`
- `backend/services/writing_service.py`
- `frontend/app/(app)/projects/[projectId]/writing/page.tsx`
- `frontend/components/writing/editor.tsx`
- `frontend/components/writing/ai-panel.tsx`

Acceptance checklist:
- User can draft manually.
- User can request AI-assisted outline or chapter draft.
- Generated output is reviewable before replacing content.
- Writing sessions are stored and visible in history.

Testing checklist:
- API tests for writing session creation.
- Service tests with mocked AI provider.
- UI tests for draft review flow.
- Job tests for queued generation.

Git commit recommendation:
- `feat: add writing workspace`

Risk assessment:
- Risk: generated output overwrites user text unexpectedly.
- Mitigation: require explicit user approval before applying generated text.

Estimated complexity:
- High

Build order:
- After project workspace.

## Milestone 09: Editing Module

Objective:
Add structured editing, analysis, revision, and approval workflows.

Tasks:
- Add editing modes and schemas.
- Add analysis and revision endpoints.
- Add side-by-side review UI.
- Add suggestion accept/reject flow.
- Add revision history.

Expected files:
- `backend/api/v1/editing.py`
- `backend/schemas/editing.py`
- `backend/services/editing_service.py`
- `frontend/app/(app)/projects/[projectId]/editing/page.tsx`
- `frontend/components/editing/revision-viewer.tsx`
- `frontend/components/editing/suggestion-panel.tsx`

Acceptance checklist:
- User can run analysis on a chapter.
- User can generate revisions.
- User can accept or reject changes.
- Chapter content only changes after approval.

Testing checklist:
- API tests for editing endpoints.
- Mock provider tests for editing outputs.
- UI tests for accept/reject.
- Regression tests for content preservation.

Git commit recommendation:
- `feat: add editing workspace`

Risk assessment:
- Risk: diff/revision UX becomes confusing.
- Mitigation: keep original and revised content clearly separated.

Estimated complexity:
- High

Build order:
- After writing module.

## Milestone 10: Prompt And Provider Infrastructure

Objective:
Formalize text AI and image provider abstractions before expanding generation features.

Tasks:
- Add AI provider registry.
- Add provider interface contracts.
- Add prompt template model.
- Add provider configuration and selection.
- Add mocked provider for tests.
- Add initial OpenAI, Anthropic, Gemini, OpenRouter adapter placeholders.
- Add Pollinations image provider adapter plan.

Expected files:
- `backend/providers/ai/base.py`
- `backend/providers/ai/registry.py`
- `backend/providers/ai/openai_provider.py`
- `backend/providers/ai/anthropic_provider.py`
- `backend/providers/ai/gemini_provider.py`
- `backend/providers/ai/openrouter_provider.py`
- `backend/providers/images/base.py`
- `backend/providers/images/pollinations_provider.py`
- `backend/models/prompt_template.py`
- `backend/schemas/prompts.py`

Acceptance checklist:
- Business services depend on provider interfaces.
- Provider can be selected from configuration or request.
- Prompt template use is traceable.
- Tests can run without real provider API keys.

Testing checklist:
- Unit tests for provider registry.
- Contract tests for mocked providers.
- Error normalization tests.
- Timeout and retry behavior tests.

Git commit recommendation:
- `feat: add prompt and provider infrastructure`

Risk assessment:
- Risk: vendor-specific behavior leaks into business services.
- Mitigation: enforce interface boundaries and normalize provider responses.

Estimated complexity:
- High

Build order:
- After initial writing/editing patterns expose provider needs.

## Milestone 11: Image Planning And Generation

Objective:
Add image planning, generation, asset review, and placement workflows.

Tasks:
- Add image plan and generated image models.
- Add image plan CRUD endpoints.
- Add image generation job endpoint.
- Add image asset grid.
- Add image approval and placement flow.
- Integrate Pollinations through image provider interface.

Expected files:
- `backend/models/image_plan.py`
- `backend/models/generated_image.py`
- `backend/api/v1/images.py`
- `backend/schemas/images.py`
- `backend/services/image_service.py`
- `frontend/app/(app)/projects/[projectId]/images/page.tsx`
- `frontend/components/images/asset-grid.tsx`
- `frontend/components/images/image-inspector.tsx`

Acceptance checklist:
- User can create image plans.
- User can generate images through provider abstraction.
- User can approve/reject images.
- User can associate images with chapters or cover workflows.

Testing checklist:
- API tests for image plans.
- Mock provider tests for image generation.
- Job tests for generation lifecycle.
- UI tests for approve/place flow.

Git commit recommendation:
- `feat: add image planning and generation`

Risk assessment:
- Risk: provider image URLs and storage strategy become brittle.
- Mitigation: separate generation metadata from asset storage policy.

Estimated complexity:
- High

Build order:
- After provider infrastructure.

## Milestone 12: Formatting Module

Objective:
Add formatting settings, preview generation, and manuscript packaging rules.

Tasks:
- Add formatting settings storage.
- Add formatting preview job.
- Add front matter and back matter settings.
- Add image placement rules.
- Add formatting workspace UI.

Expected files:
- `backend/models/formatting_settings.py`
- `backend/api/v1/formatting.py`
- `backend/schemas/formatting.py`
- `backend/services/formatting_service.py`
- `frontend/app/(app)/projects/[projectId]/formatting/page.tsx`
- `frontend/components/formatting/preview.tsx`
- `frontend/components/formatting/format-inspector.tsx`

Acceptance checklist:
- User can save formatting settings.
- User can preview formatted book structure.
- Missing formatting requirements surface as warnings.
- Formatting settings are used by export milestone later.

Testing checklist:
- API tests for formatting settings.
- Service tests for formatting package creation.
- UI tests for settings changes.
- Snapshot tests for preview data shape.

Git commit recommendation:
- `feat: add formatting workspace`

Risk assessment:
- Risk: formatting scope expands into export too early.
- Mitigation: keep preview and settings separate from final file generation.

Estimated complexity:
- Medium

Build order:
- After images.

## Milestone 13: Validation And KDP Readiness

Objective:
Add validation reports and KDP-oriented readiness checks.

Tasks:
- Add validation report model.
- Add validation rules engine.
- Add KDP profile checks.
- Add validation workspace.
- Add issue severity and fix routing.

Expected files:
- `backend/models/validation_report.py`
- `backend/api/v1/validation.py`
- `backend/schemas/validation.py`
- `backend/services/validation_service.py`
- `backend/services/validators/kdp_validator.py`
- `frontend/app/(app)/projects/[projectId]/validation/page.tsx`
- `frontend/components/validation/report.tsx`

Acceptance checklist:
- User can run validation.
- Report includes severity-ranked issues.
- Issues link to relevant workspace.
- Validation history is stored.

Testing checklist:
- Unit tests for validation rules.
- API tests for validation job lifecycle.
- UI tests for report filtering.
- Regression tests for common KDP issues.

Git commit recommendation:
- `feat: add validation and kdp readiness`

Risk assessment:
- Risk: validation may be interpreted as publishing guarantee.
- Mitigation: use clear language: guidance, not platform approval guarantee.

Estimated complexity:
- High

Build order:
- After formatting.

## Milestone 14: Cover Generator

Objective:
Add cover brief, concept generation, image selection, and cover readiness checks.

Tasks:
- Add cover brief persistence.
- Add cover concept generation flow.
- Add selected cover asset state.
- Add cover-specific validation.
- Add cover generator workspace.

Expected files:
- `backend/models/cover.py`
- `backend/api/v1/cover.py`
- `backend/schemas/cover.py`
- `backend/services/cover_service.py`
- `frontend/app/(app)/projects/[projectId]/cover/page.tsx`
- `frontend/components/cover/concept-board.tsx`
- `frontend/components/cover/cover-inspector.tsx`

Acceptance checklist:
- User can define cover brief.
- User can generate cover concepts.
- User can select approved cover image.
- Cover readiness checks integrate with validation.

Testing checklist:
- API tests for cover brief.
- Mock provider tests for concept generation.
- UI tests for selecting cover image.
- Validation tests for cover requirements.

Git commit recommendation:
- `feat: add cover generator workspace`

Risk assessment:
- Risk: cover generation overlaps image module.
- Mitigation: use image assets and image provider services rather than duplicating logic.

Estimated complexity:
- High

Build order:
- After validation and image workflows.

## Milestone 15: Marketing Module

Objective:
Add marketing pack generation and management.

Tasks:
- Add marketing pack model.
- Add KDP listing, social, email, and sales page pack types.
- Add generation endpoint.
- Add marketing workspace UI.
- Add copy/export actions for marketing content.

Expected files:
- `backend/models/marketing_pack.py`
- `backend/api/v1/marketing.py`
- `backend/schemas/marketing.py`
- `backend/services/marketing_service.py`
- `frontend/app/(app)/projects/[projectId]/marketing/page.tsx`
- `frontend/components/marketing/pack-editor.tsx`

Acceptance checklist:
- User can generate marketing packs.
- User can edit and approve pack content.
- User can copy content blocks.
- Marketing generation is traceable to provider and prompt.

Testing checklist:
- API tests for marketing pack CRUD.
- Mock provider tests for generation.
- UI tests for copy and approval actions.
- Snapshot tests for pack content schema.

Git commit recommendation:
- `feat: add marketing workspace`

Risk assessment:
- Risk: generated marketing claims become inaccurate.
- Mitigation: add user review and avoid unsupported guarantees.

Estimated complexity:
- Medium

Build order:
- After core book content and cover context exist.

## Milestone 16: Translation Module

Objective:
Add translation workflows for chapters, books, metadata, and marketing assets.

Tasks:
- Add translation model.
- Add translation job endpoint.
- Add glossary support.
- Add side-by-side translation review UI.
- Add approval workflow.

Expected files:
- `backend/models/translation.py`
- `backend/api/v1/translations.py`
- `backend/schemas/translations.py`
- `backend/services/translation_service.py`
- `frontend/app/(app)/projects/[projectId]/translation/page.tsx`
- `frontend/components/translation/translation-editor.tsx`

Acceptance checklist:
- User can request translation by scope.
- User can review source and target side by side.
- User can edit and approve translations.
- Translation records store provider and language metadata.

Testing checklist:
- API tests for translation lifecycle.
- Mock provider tests.
- UI tests for review/approve flow.
- Tests for glossary input validation.

Git commit recommendation:
- `feat: add translation workspace`

Risk assessment:
- Risk: translation quality varies across languages.
- Mitigation: include review workflow and glossary support.

Estimated complexity:
- High

Build order:
- After writing/editing and marketing structures exist.

## Milestone 17: Export Module

Objective:
Generate downloadable DOCX, PDF, and EPUB artifacts through background jobs.

Tasks:
- Add export model.
- Add export job endpoint.
- Add export renderer interfaces.
- Add DOCX renderer.
- Add PDF renderer.
- Add EPUB renderer.
- Add export workspace.
- Add download URL handling.

Expected files:
- `backend/models/export.py`
- `backend/api/v1/exports.py`
- `backend/schemas/exports.py`
- `backend/services/export_service.py`
- `backend/services/exporters/base.py`
- `backend/services/exporters/docx_exporter.py`
- `backend/services/exporters/pdf_exporter.py`
- `backend/services/exporters/epub_exporter.py`
- `frontend/app/(app)/projects/[projectId]/export/page.tsx`
- `frontend/components/export/export-checklist.tsx`

Acceptance checklist:
- User can create export jobs.
- Export status is visible.
- Completed export can be downloaded.
- Validation gates can block export when configured.
- Export history is stored.

Testing checklist:
- Unit tests for renderer interfaces.
- API tests for export lifecycle.
- File integrity tests for generated artifacts.
- Job tests for failed export recovery.

Git commit recommendation:
- `feat: add export workflow`

Risk assessment:
- Risk: export rendering is complex and format-specific.
- Mitigation: isolate renderer interfaces and test each output format separately.

Estimated complexity:
- Very High

Build order:
- After formatting, validation, images, and cover.

## Milestone 18: History, Notifications, And Jobs

Objective:
Make system activity, async work, and user-facing updates reliable and visible.

Tasks:
- Add job model and worker processing.
- Add job logs.
- Add audit/history event model.
- Add notifications model.
- Add job status UI.
- Add notification popover.
- Add history timelines.

Expected files:
- `backend/models/job.py`
- `backend/models/job_log.py`
- `backend/models/audit_log.py`
- `backend/models/notification.py`
- `backend/api/v1/jobs.py`
- `backend/api/v1/history.py`
- `backend/api/v1/notifications.py`
- `backend/workers/main.py`
- `frontend/components/jobs/job-progress.tsx`
- `frontend/components/notifications/notification-popover.tsx`
- `frontend/app/(app)/projects/[projectId]/history/page.tsx`

Acceptance checklist:
- Long-running tasks create jobs.
- Job logs are visible.
- User gets notifications for important completions/failures.
- Project history shows meaningful events.

Testing checklist:
- Worker tests for job execution.
- API tests for jobs and notifications.
- UI tests for progress and notification read states.
- Audit/history event tests.

Git commit recommendation:
- `feat: add jobs history and notifications`

Risk assessment:
- Risk: job state becomes inconsistent across modules.
- Mitigation: use a single job state machine and shared service.

Estimated complexity:
- High

Build order:
- Some foundations may appear earlier; complete this after major async modules exist.

## Milestone 19: Settings, API Keys, And Admin Foundations

Objective:
Add user preferences, provider settings, API key management, and admin visibility foundations.

Tasks:
- Add settings model and endpoints.
- Add API key model and secure hashing.
- Add settings pages.
- Add provider preference UI.
- Add admin route guard.
- Add basic admin diagnostics pages.

Expected files:
- `backend/models/settings.py`
- `backend/models/api_key.py`
- `backend/api/v1/settings.py`
- `backend/api/v1/api_keys.py`
- `backend/api/v1/admin.py`
- `backend/services/api_key_service.py`
- `frontend/app/(app)/settings/page.tsx`
- `frontend/components/settings/api-keys.tsx`
- `frontend/app/(app)/admin/page.tsx`

Acceptance checklist:
- User can update settings.
- User can create and revoke API keys.
- Raw API key is only shown once.
- Admin pages require admin role.

Testing checklist:
- API tests for settings.
- Security tests for API key hashing.
- Authorization tests for admin routes.
- UI tests for API key creation and revoke confirmation.

Git commit recommendation:
- `feat: add settings api keys and admin foundations`

Risk assessment:
- Risk: API keys create a new attack surface.
- Mitigation: hash keys, scope keys, allow revocation, log usage.

Estimated complexity:
- High

Build order:
- After auth and core user flows.

## Milestone 20: Billing And Usage Controls

Objective:
Prepare commercial SaaS controls for subscriptions, limits, and provider cost management.

Tasks:
- Choose billing provider.
- Add subscription state model.
- Add usage event tracking.
- Add plan limits.
- Add rate limit enforcement.
- Add billing settings page.
- Add provider cost reporting.

Expected files:
- `backend/models/subscription.py`
- `backend/models/usage_event.py`
- `backend/api/v1/billing.py`
- `backend/services/billing_service.py`
- `backend/services/usage_service.py`
- `backend/middleware/rate_limit.py`
- `frontend/app/(app)/settings/billing/page.tsx`
- `docs/Security.md`

Acceptance checklist:
- User plan can be represented.
- Usage is tracked for AI/image/export operations.
- Limits can block or warn before expensive actions.
- Billing webhooks are planned and secured.

Testing checklist:
- Unit tests for usage calculations.
- API tests for billing state.
- Rate limit tests.
- Webhook signature verification tests when billing provider is added.

Git commit recommendation:
- `feat: add billing and usage controls`

Risk assessment:
- Risk: billing mistakes directly affect revenue and trust.
- Mitigation: build auditability, test webhooks, and keep manual admin overrides.

Estimated complexity:
- Very High

Build order:
- Before public production launch.

## Milestone 21: End-To-End QA And Hardening

Objective:
Stabilize the full product before staging and production deployment.

Tasks:
- Add end-to-end tests for critical workflows.
- Add accessibility checks.
- Add security review.
- Add performance profiling.
- Add provider failure simulations.
- Add backup and restore rehearsal.
- Add error monitoring.

Expected files:
- `frontend/tests/e2e/*`
- `backend/tests/integration/*`
- `docs/Testing_Checklist.md`
- `docs/Security.md`
- `docs/Deployment.md`

Acceptance checklist:
- Core workflow passes end to end.
- Cross-user access tests pass.
- Accessibility baseline is met.
- Provider failures degrade gracefully.
- No known critical security gaps remain.

Testing checklist:
- Login to export E2E.
- Project ownership E2E.
- Export generation E2E.
- AI provider failure tests.
- Image provider failure tests.
- Accessibility audit.
- Load smoke test.

Git commit recommendation:
- `test: add end-to-end qa and hardening checks`

Risk assessment:
- Risk: late integration issues expose architectural gaps.
- Mitigation: run integration checks continuously from earlier milestones.

Estimated complexity:
- Very High

Build order:
- After all product modules exist.

## Milestone 22: Staging Deployment

Objective:
Deploy a production-like staging environment for full validation before public launch.

Tasks:
- Configure Neon staging database.
- Configure Render staging backend.
- Configure Cloudflare Pages staging frontend.
- Configure environment variables.
- Run migrations.
- Configure logs and monitoring.
- Run smoke tests.
- Validate worker deployment.

Expected files:
- `docs/Deployment.md`
- `.github/workflows/deploy-staging.yml`
- `render.yaml` if Render Blueprints are selected
- `frontend/wrangler.toml` if Cloudflare configuration requires it

Acceptance checklist:
- Staging frontend is reachable.
- Staging backend is reachable.
- Staging database connects successfully.
- Workers process jobs.
- Smoke tests pass.
- Secrets are stored outside Git.

Testing checklist:
- Health check.
- Auth flow.
- Project create flow.
- AI mock or limited provider smoke test.
- Export smoke test.
- Worker smoke test.
- Log and error capture check.

Git commit recommendation:
- `chore: configure staging deployment`

Risk assessment:
- Risk: environment drift between local and staging.
- Mitigation: document variables and use deployment templates where possible.

Estimated complexity:
- High

Build order:
- After QA hardening.

## Milestone 23: Production Deployment

Objective:
Launch AI Ebook Studio to production with monitoring, rollback, security, and operational readiness.

Tasks:
- Configure Neon production database.
- Configure Render production backend.
- Configure Cloudflare Pages production frontend.
- Configure production secrets.
- Configure custom domains.
- Configure backups and retention.
- Configure monitoring and alerts.
- Run production migration plan.
- Run production smoke tests.
- Prepare rollback plan.
- Prepare launch checklist.

Expected files:
- `docs/Deployment.md`
- `docs/Security.md`
- `.github/workflows/deploy-production.yml`
- `render.yaml` if used
- Production launch checklist documentation

Acceptance checklist:
- Production frontend is live.
- Production backend is healthy.
- Production database migrations complete.
- Monitoring and alerts are active.
- Backups are verified.
- Rollback plan is documented.
- Initial admin account is secured.
- Production smoke tests pass.

Testing checklist:
- Production health checks.
- Auth smoke test.
- Create project smoke test.
- Job worker smoke test.
- Export smoke test.
- Permission boundary smoke test.
- Error monitoring smoke test.
- Backup restore rehearsal documented.

Git commit recommendation:
- `chore: prepare production deployment`

Risk assessment:
- Risk: production launch failure affects users and trust.
- Mitigation: launch behind limited access, monitor closely, and keep rollback steps ready.

Estimated complexity:
- Very High

Build order:
- Final milestone.

## Recommended Release Phases

### Private Alpha

Scope:
- Auth
- Projects
- Books
- Chapters
- Writing
- Editing
- Basic jobs/history

Goal:
Validate core writing workflow with trusted users.

### Private Beta

Scope:
- Images
- Formatting
- Validation
- Cover
- Export

Goal:
Validate complete publishing workflow.

### Public Beta

Scope:
- Marketing
- Translation
- Settings
- Usage controls
- Improved reliability

Goal:
Validate commercial demand and pricing.

### Production Launch

Scope:
- Billing
- Monitoring
- Security hardening
- Support readiness
- Production deployment

Goal:
Launch as a reliable commercial SaaS product.

## Cross-Cutting Requirements For Every Milestone

Acceptance:
- Documentation updated.
- Type checks pass.
- Tests are added or explicitly deferred with rationale.
- No provider-specific logic leaks across abstraction boundaries.
- User-owned resources enforce authorization.

Testing:
- Unit tests for business logic.
- API tests for endpoint behavior.
- UI tests for critical flows.
- Integration tests for cross-module behavior.
- Regression tests for bugs found during review.

Security:
- No secrets committed.
- No raw provider payloads exposed unnecessarily.
- No cross-user access.
- Destructive actions require confirmation.

UX:
- Responsive behavior considered.
- Loading, empty, error, and success states designed.
- AI outputs require user review before final application.

## Final Production Readiness Checklist

- CI passes.
- Staging smoke tests pass.
- Production secrets configured.
- Database backups enabled.
- Migration rollback strategy documented.
- Error monitoring active.
- Logs structured and searchable.
- Rate limits active.
- Billing controls active.
- Admin access secured.
- Support process documented.
- Terms, privacy, and user data policies prepared.
