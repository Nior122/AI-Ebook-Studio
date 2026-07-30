# REST API Design

## Purpose

This document defines the planned REST API for AI Ebook Studio.

It is documentation only. It does not implement FastAPI routes, request handlers, schemas, services, authentication, or business logic. Future implementation stages should translate this contract into OpenAPI-backed FastAPI endpoints.

## API Style

Base URL:

```text
/api/v1
```

Format:
- JSON request bodies
- JSON response bodies
- REST resource naming
- Bearer token authentication for protected endpoints
- Async jobs for long-running AI, image, validation, translation, formatting, and export operations

Versioning:
- Initial version: `v1`
- Breaking API changes should use a new version prefix.

## Authentication Model

Planned protected endpoints use:

```http
Authorization: Bearer <access_token>
```

Public endpoints:
- Login
- Registration
- Password reset request
- Password reset confirmation
- Token refresh if refresh token is cookie-based or explicitly supplied

Admin endpoints:
- Require authenticated user with administrator role.

Future team workspace endpoints:
- Require workspace role checks in addition to authentication.

## Standard Headers

Request headers:

```http
Content-Type: application/json
Accept: application/json
Authorization: Bearer <access_token>
Idempotency-Key: <uuid> # recommended for create/export/generation/job endpoints
```

Response headers:

```http
Content-Type: application/json
X-Request-ID: <request-id>
```

## Standard Response Envelopes

Single resource:

```json
{
  "data": {}
}
```

List resource:

```json
{
  "data": [],
  "pagination": {
    "page": 1,
    "page_size": 25,
    "total": 120,
    "has_next": true
  }
}
```

Accepted async job:

```json
{
  "data": {
    "job_id": "job_123",
    "status": "queued"
  }
}
```

Error:

```json
{
  "error": {
    "code": "validation_error",
    "message": "Request validation failed.",
    "details": {
      "field": "title"
    }
  }
}
```

## Common Error Codes

| Status | Code | Meaning |
|---:|---|---|
| 400 | `bad_request` | Invalid request shape or unsupported operation |
| 401 | `unauthorized` | Missing or invalid authentication |
| 403 | `forbidden` | Authenticated but not allowed |
| 404 | `not_found` | Resource does not exist or is not visible to user |
| 409 | `conflict` | Duplicate or invalid state transition |
| 422 | `validation_error` | Field-level validation failed |
| 429 | `rate_limited` | Too many requests or provider usage exceeded |
| 500 | `internal_error` | Unexpected server error |
| 502 | `provider_error` | External AI/image/storage provider failed |
| 503 | `service_unavailable` | Service temporarily unavailable |

## Shared Object Summaries

These summaries are not final schemas. They define the expected shape for API planning.

### User

```json
{
  "id": "usr_123",
  "email": "author@example.com",
  "display_name": "Example Author",
  "role": "user",
  "status": "active",
  "created_at": "2026-07-07T12:00:00Z"
}
```

### Project

```json
{
  "id": "prj_123",
  "name": "Healthy Meal Prep Guide",
  "title": "Healthy Meal Prep",
  "genre": "Nonfiction",
  "primary_language": "en",
  "status": "draft",
  "created_at": "2026-07-07T12:00:00Z",
  "updated_at": "2026-07-07T12:00:00Z"
}
```

### Book

```json
{
  "id": "book_123",
  "project_id": "prj_123",
  "title": "Healthy Meal Prep",
  "author_name": "Example Author",
  "language": "en",
  "status": "draft",
  "word_count": 18000
}
```

### Chapter

```json
{
  "id": "ch_123",
  "book_id": "book_123",
  "title": "Getting Started",
  "position": 1,
  "status": "draft",
  "word_count": 1200
}
```

### Job

```json
{
  "id": "job_123",
  "type": "export",
  "status": "queued",
  "progress": 0,
  "created_at": "2026-07-07T12:00:00Z"
}
```

## Endpoint Catalog

### Authentication

#### Register

```yaml
method: POST
url: /api/v1/auth/register
auth: Public
description: Create a new registered user account.
request:
  email: string
  password: string
  display_name: string
response:
  data:
    user: User
    access_token: string
    refresh_token: string
errors:
  - 409 conflict
  - 422 validation_error
example_request:
  email: author@example.com
  password: "********"
  display_name: Example Author
example_response:
  data:
    user:
      id: usr_123
      email: author@example.com
      display_name: Example Author
      role: user
    access_token: jwt-access-token
    refresh_token: jwt-refresh-token
```

#### Login

```yaml
method: POST
url: /api/v1/auth/login
auth: Public
description: Authenticate a user and issue tokens.
request:
  email: string
  password: string
response:
  data:
    user: User
    access_token: string
    refresh_token: string
errors:
  - 401 unauthorized
  - 422 validation_error
example_request:
  email: author@example.com
  password: "********"
example_response:
  data:
    user:
      id: usr_123
      email: author@example.com
    access_token: jwt-access-token
    refresh_token: jwt-refresh-token
```

#### Refresh Token

```yaml
method: POST
url: /api/v1/auth/refresh
auth: Public or refresh-token cookie
description: Exchange a valid refresh token for a new access token.
request:
  refresh_token: string
response:
  data:
    access_token: string
    refresh_token: string
errors:
  - 401 unauthorized
  - 422 validation_error
example_request:
  refresh_token: jwt-refresh-token
example_response:
  data:
    access_token: new-jwt-access-token
    refresh_token: new-jwt-refresh-token
```

#### Logout

```yaml
method: POST
url: /api/v1/auth/logout
auth: Required
description: Revoke the current session or refresh token.
request:
  refresh_token: string
response:
  data:
    success: boolean
errors:
  - 401 unauthorized
example_request:
  refresh_token: jwt-refresh-token
example_response:
  data:
    success: true
```

#### Get Current User

```yaml
method: GET
url: /api/v1/auth/me
auth: Required
description: Return the authenticated user's profile.
request: none
response:
  data: User
errors:
  - 401 unauthorized
example_request: none
example_response:
  data:
    id: usr_123
    email: author@example.com
    display_name: Example Author
    role: user
```

#### Request Password Reset

```yaml
method: POST
url: /api/v1/auth/password-reset/request
auth: Public
description: Request a password reset email if the account exists.
request:
  email: string
response:
  data:
    accepted: boolean
errors:
  - 422 validation_error
example_request:
  email: author@example.com
example_response:
  data:
    accepted: true
```

#### Confirm Password Reset

```yaml
method: POST
url: /api/v1/auth/password-reset/confirm
auth: Public
description: Reset a password using a valid reset token.
request:
  token: string
  new_password: string
response:
  data:
    success: boolean
errors:
  - 400 bad_request
  - 422 validation_error
example_request:
  token: reset-token
  new_password: "********"
example_response:
  data:
    success: true
```

### Projects

#### List Projects

```yaml
method: GET
url: /api/v1/projects
auth: Required
description: List projects owned by or visible to the authenticated user.
request:
  query:
    page: integer
    page_size: integer
    status: string
    search: string
response:
  data: Project[]
  pagination: Pagination
errors:
  - 401 unauthorized
example_request: /api/v1/projects?page=1&page_size=25&status=draft
example_response:
  data:
    - id: prj_123
      name: Healthy Meal Prep Guide
      status: draft
```

#### Create Project

```yaml
method: POST
url: /api/v1/projects
auth: Required
description: Create a new ebook project workspace.
request:
  name: string
  title: string
  subtitle: string
  genre: string
  target_audience: string
  primary_language: string
  publishing_goal: string
response:
  data: Project
errors:
  - 401 unauthorized
  - 422 validation_error
example_request:
  name: Healthy Meal Prep Guide
  title: Healthy Meal Prep
  genre: Nonfiction
  primary_language: en
example_response:
  data:
    id: prj_123
    name: Healthy Meal Prep Guide
    status: draft
```

#### Get Project

```yaml
method: GET
url: /api/v1/projects/{project_id}
auth: Required
description: Retrieve one project and summary state.
request:
  path:
    project_id: string
response:
  data: Project
errors:
  - 401 unauthorized
  - 403 forbidden
  - 404 not_found
example_request: /api/v1/projects/prj_123
example_response:
  data:
    id: prj_123
    name: Healthy Meal Prep Guide
    status: draft
```

#### Update Project

```yaml
method: PATCH
url: /api/v1/projects/{project_id}
auth: Required
description: Update editable project metadata.
request:
  title: string
  subtitle: string
  genre: string
  target_audience: string
  publishing_goal: string
  status: string
response:
  data: Project
errors:
  - 401 unauthorized
  - 403 forbidden
  - 404 not_found
  - 422 validation_error
example_request:
  title: Healthy Meal Prep for Busy People
example_response:
  data:
    id: prj_123
    title: Healthy Meal Prep for Busy People
```

#### Archive Project

```yaml
method: POST
url: /api/v1/projects/{project_id}/archive
auth: Required
description: Archive a project without permanently deleting it.
request:
  path:
    project_id: string
response:
  data:
    id: string
    status: archived
errors:
  - 401 unauthorized
  - 403 forbidden
  - 404 not_found
example_request: /api/v1/projects/prj_123/archive
example_response:
  data:
    id: prj_123
    status: archived
```

#### Delete Project

```yaml
method: DELETE
url: /api/v1/projects/{project_id}
auth: Required
description: Soft delete a project.
request:
  path:
    project_id: string
response:
  data:
    deleted: boolean
errors:
  - 401 unauthorized
  - 403 forbidden
  - 404 not_found
  - 409 conflict
example_request: /api/v1/projects/prj_123
example_response:
  data:
    deleted: true
```

### Books

#### List Books

```yaml
method: GET
url: /api/v1/projects/{project_id}/books
auth: Required
description: List books or editions within a project.
request:
  path:
    project_id: string
response:
  data: Book[]
errors:
  - 401 unauthorized
  - 403 forbidden
  - 404 not_found
example_request: /api/v1/projects/prj_123/books
example_response:
  data:
    - id: book_123
      title: Healthy Meal Prep
      status: draft
```

#### Create Book

```yaml
method: POST
url: /api/v1/projects/{project_id}/books
auth: Required
description: Create a book record inside a project.
request:
  title: string
  subtitle: string
  author_name: string
  language: string
  book_type: string
response:
  data: Book
errors:
  - 401 unauthorized
  - 403 forbidden
  - 404 not_found
  - 422 validation_error
example_request:
  title: Healthy Meal Prep
  author_name: Example Author
  language: en
example_response:
  data:
    id: book_123
    project_id: prj_123
    title: Healthy Meal Prep
```

#### Get Book

```yaml
method: GET
url: /api/v1/books/{book_id}
auth: Required
description: Retrieve a book and summary metadata.
request:
  path:
    book_id: string
response:
  data: Book
errors:
  - 401 unauthorized
  - 403 forbidden
  - 404 not_found
example_request: /api/v1/books/book_123
example_response:
  data:
    id: book_123
    title: Healthy Meal Prep
```

#### Update Book

```yaml
method: PATCH
url: /api/v1/books/{book_id}
auth: Required
description: Update book metadata.
request:
  title: string
  subtitle: string
  author_name: string
  description: string
  status: string
response:
  data: Book
errors:
  - 401 unauthorized
  - 403 forbidden
  - 404 not_found
  - 422 validation_error
example_request:
  status: editing
example_response:
  data:
    id: book_123
    status: editing
```

#### Delete Book

```yaml
method: DELETE
url: /api/v1/books/{book_id}
auth: Required
description: Soft delete a book and hide its chapters from active views.
request:
  path:
    book_id: string
response:
  data:
    deleted: boolean
errors:
  - 401 unauthorized
  - 403 forbidden
  - 404 not_found
  - 409 conflict
example_request: /api/v1/books/book_123
example_response:
  data:
    deleted: true
```

#### List Chapters

```yaml
method: GET
url: /api/v1/books/{book_id}/chapters
auth: Required
description: List ordered chapters for a book.
request:
  path:
    book_id: string
response:
  data: Chapter[]
errors:
  - 401 unauthorized
  - 403 forbidden
  - 404 not_found
example_request: /api/v1/books/book_123/chapters
example_response:
  data:
    - id: ch_123
      title: Getting Started
      position: 1
```

#### Create Chapter

```yaml
method: POST
url: /api/v1/books/{book_id}/chapters
auth: Required
description: Create a chapter in a book.
request:
  title: string
  position: integer
  summary: string
response:
  data: Chapter
errors:
  - 401 unauthorized
  - 403 forbidden
  - 404 not_found
  - 422 validation_error
example_request:
  title: Getting Started
  position: 1
  summary: Opening chapter
example_response:
  data:
    id: ch_123
    title: Getting Started
```

#### Get Chapter

```yaml
method: GET
url: /api/v1/chapters/{chapter_id}
auth: Required
description: Retrieve a chapter including its structured document subtree.
request:
  path:
    chapter_id: string
response:
  data: Chapter
errors:
  - 401 unauthorized
  - 403 forbidden
  - 404 not_found
example_request: /api/v1/chapters/ch_123
example_response:
  data:
    id: ch_123
    title: Getting Started
    sections:
      - id: sec_001
        title: Why This Matters
```

#### Update Chapter

```yaml
method: PATCH
url: /api/v1/chapters/{chapter_id}
auth: Required
description: Update chapter metadata such as title, ordering, summary, or status. Structured prose is managed through document-aware writing and editing endpoints.
request:
  title: string
  position: integer
  summary: string
  status: string
response:
  data: Chapter
errors:
  - 401 unauthorized
  - 403 forbidden
  - 404 not_found
  - 409 conflict
  - 422 validation_error
example_request:
  status: approved
example_response:
  data:
    id: ch_123
    status: approved
```

#### Delete Chapter

```yaml
method: DELETE
url: /api/v1/chapters/{chapter_id}
auth: Required
description: Soft delete a chapter.
request:
  path:
    chapter_id: string
response:
  data:
    deleted: boolean
errors:
  - 401 unauthorized
  - 403 forbidden
  - 404 not_found
example_request: /api/v1/chapters/ch_123
example_response:
  data:
    deleted: true
```

### Writing

#### Generate Outline

```yaml
method: POST
url: /api/v1/projects/{project_id}/writing/outline
auth: Required
description: Start an async job to generate a book outline.
request:
  book_id: string
  brief: string
  audience: string
  tone: string
  chapter_count: integer
  provider: string
response:
  data:
    job_id: string
    status: queued
errors:
  - 401 unauthorized
  - 403 forbidden
  - 404 not_found
  - 422 validation_error
  - 429 rate_limited
  - 502 provider_error
example_request:
  book_id: book_123
  brief: A practical meal prep guide
  chapter_count: 10
example_response:
  data:
    job_id: job_123
    status: queued
```

#### Generate Chapter Draft

```yaml
method: POST
url: /api/v1/chapters/{chapter_id}/writing/draft
auth: Required
description: Start an async writing session to draft or replace structured chapter nodes.
request:
  instruction: string
  outline_context: string
  tone: string
  target_word_count: integer
  provider: string
  prompt_template_id: string
response:
  data:
    job_id: string
    writing_session_id: string
    status: queued
errors:
  - 401 unauthorized
  - 403 forbidden
  - 404 not_found
  - 422 validation_error
  - 429 rate_limited
  - 502 provider_error
example_request:
  instruction: Draft this chapter for beginners.
  target_word_count: 1200
example_response:
  data:
    job_id: job_124
    writing_session_id: ws_123
    status: queued
```

#### Rewrite Chapter Content

```yaml
method: POST
url: /api/v1/chapters/{chapter_id}/writing/rewrite
auth: Required
description: Start an async rewrite job for an existing chapter, section, paragraph, or sentence subtree.
request:
  instruction: string
  target_node_id: string
  rewrite_mode: string
  provider: string
response:
  data:
    job_id: string
    writing_session_id: string
    status: queued
errors:
  - 401 unauthorized
  - 403 forbidden
  - 404 not_found
  - 422 validation_error
  - 429 rate_limited
example_request:
  instruction: Make this clearer and more practical.
  target_node_id: sent_001
  rewrite_mode: clarity
example_response:
  data:
    job_id: job_125
    writing_session_id: ws_124
    status: queued
```

#### List Writing Sessions

```yaml
method: GET
url: /api/v1/projects/{project_id}/writing/sessions
auth: Required
description: List writing sessions for a project.
request:
  query:
    book_id: string
    chapter_id: string
    session_type: string
    page: integer
    page_size: integer
response:
  data: WritingSession[]
  pagination: Pagination
errors:
  - 401 unauthorized
  - 403 forbidden
  - 404 not_found
example_request: /api/v1/projects/prj_123/writing/sessions?chapter_id=ch_123
example_response:
  data:
    - id: ws_123
      session_type: draft
      status: completed
```

#### Get Writing Session

```yaml
method: GET
url: /api/v1/writing/sessions/{session_id}
auth: Required
description: Retrieve a writing session and its output.
request:
  path:
    session_id: string
response:
  data: WritingSession
errors:
  - 401 unauthorized
  - 403 forbidden
  - 404 not_found
example_request: /api/v1/writing/sessions/ws_123
example_response:
  data:
    id: ws_123
    status: completed
    output_document:
      root_node_id: book_123
      changed_node_ids:
        - ch_123
```

### Editing

#### Analyze Chapter

```yaml
method: POST
url: /api/v1/chapters/{chapter_id}/editing/analyze
auth: Required
description: Analyze chapter quality, clarity, structure, and consistency.
request:
  analysis_types: string[]
  provider: string
response:
  data:
    job_id: string
    status: queued
errors:
  - 401 unauthorized
  - 403 forbidden
  - 404 not_found
  - 429 rate_limited
example_request:
  analysis_types:
    - clarity
    - readability
example_response:
  data:
    job_id: job_201
    status: queued
```

#### Edit Chapter

```yaml
method: POST
url: /api/v1/chapters/{chapter_id}/editing/revise
auth: Required
description: Generate an edited revision of a structured document subtree.
request:
  edit_mode: string
  instruction: string
  preserve_voice: boolean
  provider: string
response:
  data:
    job_id: string
    writing_session_id: string
    status: queued
errors:
  - 401 unauthorized
  - 403 forbidden
  - 404 not_found
  - 422 validation_error
  - 429 rate_limited
example_request:
  edit_mode: line_edit
  preserve_voice: true
example_response:
  data:
    job_id: job_202
    writing_session_id: ws_202
    status: queued
```

#### Accept Editing Revision

```yaml
method: POST
url: /api/v1/editing/revisions/{session_id}/accept
auth: Required
description: Apply an editing session output to the target chapter.
request:
  apply_mode: string
response:
  data: Chapter
errors:
  - 401 unauthorized
  - 403 forbidden
  - 404 not_found
  - 409 conflict
example_request:
  apply_mode: replace_chapter
example_response:
  data:
    id: ch_123
    status: draft
```

#### Reject Editing Revision

```yaml
method: POST
url: /api/v1/editing/revisions/{session_id}/reject
auth: Required
description: Mark an editing revision as rejected without applying it.
request:
  reason: string
response:
  data:
    id: string
    status: rejected
errors:
  - 401 unauthorized
  - 403 forbidden
  - 404 not_found
example_request:
  reason: Too formal
example_response:
  data:
    id: ws_202
    status: rejected
```

### Images

#### List Image Plans

```yaml
method: GET
url: /api/v1/projects/{project_id}/image-plans
auth: Required
description: List image plans for a project.
request:
  query:
    image_type: string
    status: string
response:
  data: ImagePlan[]
errors:
  - 401 unauthorized
  - 403 forbidden
  - 404 not_found
example_request: /api/v1/projects/prj_123/image-plans?image_type=chapter
example_response:
  data:
    - id: imgplan_123
      title: Chapter 1 illustration
      status: planned
```

#### Create Image Plan

```yaml
method: POST
url: /api/v1/projects/{project_id}/image-plans
auth: Required
description: Create a planned image requirement before generation.
request:
  book_id: string
  chapter_id: string
  title: string
  image_type: string
  description: string
  style_direction: string
  aspect_ratio: string
  placement_notes: string
response:
  data: ImagePlan
errors:
  - 401 unauthorized
  - 403 forbidden
  - 404 not_found
  - 422 validation_error
example_request:
  title: Chapter 1 hero image
  image_type: chapter
  description: Bright kitchen meal prep scene
example_response:
  data:
    id: imgplan_123
    status: planned
```

#### Update Image Plan

```yaml
method: PATCH
url: /api/v1/image-plans/{image_plan_id}
auth: Required
description: Update an image plan before or after generation.
request:
  title: string
  description: string
  style_direction: string
  aspect_ratio: string
  status: string
response:
  data: ImagePlan
errors:
  - 401 unauthorized
  - 403 forbidden
  - 404 not_found
  - 422 validation_error
example_request:
  status: approved
example_response:
  data:
    id: imgplan_123
    status: approved
```

#### Generate Image

```yaml
method: POST
url: /api/v1/image-plans/{image_plan_id}/generate
auth: Required
description: Start an async image generation job through the image provider layer.
request:
  provider: string
  prompt: string
  negative_prompt: string
  width: integer
  height: integer
  seed: string
response:
  data:
    job_id: string
    status: queued
errors:
  - 401 unauthorized
  - 403 forbidden
  - 404 not_found
  - 422 validation_error
  - 429 rate_limited
  - 502 provider_error
example_request:
  provider: pollinations
  prompt: Bright editorial food photography scene
  width: 1024
  height: 1024
example_response:
  data:
    job_id: job_301
    status: queued
```

#### List Generated Images

```yaml
method: GET
url: /api/v1/projects/{project_id}/generated-images
auth: Required
description: List generated image assets for a project.
request:
  query:
    image_plan_id: string
    status: string
    usage_context: string
response:
  data: GeneratedImage[]
  pagination: Pagination
errors:
  - 401 unauthorized
  - 403 forbidden
  - 404 not_found
example_request: /api/v1/projects/prj_123/generated-images?status=approved
example_response:
  data:
    - id: img_123
      asset_url: https://cdn.example.com/image.png
      status: approved
```

#### Update Generated Image

```yaml
method: PATCH
url: /api/v1/generated-images/{image_id}
auth: Required
description: Approve, reject, archive, or update metadata for a generated image.
request:
  status: string
  usage_context: string
  placement_notes: string
response:
  data: GeneratedImage
errors:
  - 401 unauthorized
  - 403 forbidden
  - 404 not_found
  - 422 validation_error
example_request:
  status: approved
example_response:
  data:
    id: img_123
    status: approved
```

### Formatting

#### Get Formatting Settings

```yaml
method: GET
url: /api/v1/books/{book_id}/formatting
auth: Required
description: Retrieve formatting settings for a book.
request:
  path:
    book_id: string
response:
  data:
    trim_size: string
    heading_style: string
    front_matter: object
    back_matter: object
    image_rules: object
errors:
  - 401 unauthorized
  - 403 forbidden
  - 404 not_found
example_request: /api/v1/books/book_123/formatting
example_response:
  data:
    trim_size: "6x9"
    heading_style: standard
```

#### Update Formatting Settings

```yaml
method: PUT
url: /api/v1/books/{book_id}/formatting
auth: Required
description: Replace formatting settings for a book.
request:
  trim_size: string
  heading_style: string
  front_matter: object
  back_matter: object
  image_rules: object
response:
  data:
    trim_size: string
    heading_style: string
    front_matter: object
    back_matter: object
    image_rules: object
errors:
  - 401 unauthorized
  - 403 forbidden
  - 404 not_found
  - 422 validation_error
example_request:
  trim_size: "6x9"
  heading_style: standard
example_response:
  data:
    trim_size: "6x9"
    heading_style: standard
```

#### Preview Formatting

```yaml
method: POST
url: /api/v1/books/{book_id}/formatting/preview
auth: Required
description: Start an async formatting preview job.
request:
  format: string
  include_images: boolean
response:
  data:
    job_id: string
    status: queued
errors:
  - 401 unauthorized
  - 403 forbidden
  - 404 not_found
  - 422 validation_error
example_request:
  format: pdf
  include_images: true
example_response:
  data:
    job_id: job_401
    status: queued
```

### Validation

#### Run Validation

```yaml
method: POST
url: /api/v1/books/{book_id}/validation/run
auth: Required
description: Start an async validation job for manuscript, formatting, cover, metadata, and export readiness.
request:
  validation_profile: string
  include_kdp_checks: boolean
response:
  data:
    job_id: string
    status: queued
errors:
  - 401 unauthorized
  - 403 forbidden
  - 404 not_found
  - 422 validation_error
example_request:
  validation_profile: kdp
  include_kdp_checks: true
example_response:
  data:
    job_id: job_501
    status: queued
```

#### Get Latest Validation Report

```yaml
method: GET
url: /api/v1/books/{book_id}/validation/latest
auth: Required
description: Retrieve the latest validation report for a book.
request:
  path:
    book_id: string
response:
  data:
    id: string
    status: string
    score: integer
    issues: object[]
    created_at: string
errors:
  - 401 unauthorized
  - 403 forbidden
  - 404 not_found
example_request: /api/v1/books/book_123/validation/latest
example_response:
  data:
    id: val_123
    status: warning
    score: 82
    issues: []
```

#### List Validation Reports

```yaml
method: GET
url: /api/v1/books/{book_id}/validation/reports
auth: Required
description: List historical validation reports for a book.
request:
  query:
    page: integer
    page_size: integer
response:
  data: ValidationReport[]
  pagination: Pagination
errors:
  - 401 unauthorized
  - 403 forbidden
  - 404 not_found
example_request: /api/v1/books/book_123/validation/reports
example_response:
  data:
    - id: val_123
      status: warning
      score: 82
```

### Cover

#### Get Cover Brief

```yaml
method: GET
url: /api/v1/books/{book_id}/cover
auth: Required
description: Retrieve cover brief and selected cover asset state.
request:
  path:
    book_id: string
response:
  data:
    brief: object
    selected_image_id: string
    status: string
errors:
  - 401 unauthorized
  - 403 forbidden
  - 404 not_found
example_request: /api/v1/books/book_123/cover
example_response:
  data:
    brief:
      genre: Nonfiction
      mood: clean
    status: draft
```

#### Update Cover Brief

```yaml
method: PUT
url: /api/v1/books/{book_id}/cover
auth: Required
description: Create or replace the cover brief for a book.
request:
  genre: string
  audience: string
  mood: string
  typography_notes: string
  visual_references: string[]
  marketplace_constraints: object
response:
  data:
    brief: object
    status: string
errors:
  - 401 unauthorized
  - 403 forbidden
  - 404 not_found
  - 422 validation_error
example_request:
  genre: Nonfiction
  mood: clean editorial
example_response:
  data:
    brief:
      genre: Nonfiction
      mood: clean editorial
    status: draft
```

#### Generate Cover Concepts

```yaml
method: POST
url: /api/v1/books/{book_id}/cover/concepts
auth: Required
description: Start an async job to generate cover concepts or cover image prompts.
request:
  provider: string
  concept_count: integer
  include_image_prompts: boolean
response:
  data:
    job_id: string
    status: queued
errors:
  - 401 unauthorized
  - 403 forbidden
  - 404 not_found
  - 429 rate_limited
example_request:
  concept_count: 3
  include_image_prompts: true
example_response:
  data:
    job_id: job_601
    status: queued
```

#### Select Cover Image

```yaml
method: POST
url: /api/v1/books/{book_id}/cover/select-image
auth: Required
description: Select a generated image as the active cover image.
request:
  image_id: string
response:
  data:
    selected_image_id: string
    status: string
errors:
  - 401 unauthorized
  - 403 forbidden
  - 404 not_found
  - 409 conflict
example_request:
  image_id: img_123
example_response:
  data:
    selected_image_id: img_123
    status: selected
```

### Translation

#### List Translations

```yaml
method: GET
url: /api/v1/projects/{project_id}/translations
auth: Required
description: List translation records for a project.
request:
  query:
    book_id: string
    chapter_id: string
    target_language: string
    status: string
response:
  data: Translation[]
  pagination: Pagination
errors:
  - 401 unauthorized
  - 403 forbidden
  - 404 not_found
example_request: /api/v1/projects/prj_123/translations?target_language=es
example_response:
  data:
    - id: tr_123
      target_language: es
      status: translated
```

#### Create Translation Job

```yaml
method: POST
url: /api/v1/books/{book_id}/translations
auth: Required
description: Start an async translation job for a book, chapter, metadata, or marketing content.
request:
  scope: string
  chapter_id: string
  source_language: string
  target_language: string
  glossary: object
  provider: string
response:
  data:
    job_id: string
    status: queued
errors:
  - 401 unauthorized
  - 403 forbidden
  - 404 not_found
  - 422 validation_error
  - 429 rate_limited
example_request:
  scope: chapter
  chapter_id: ch_123
  source_language: en
  target_language: es
example_response:
  data:
    job_id: job_701
    status: queued
```

#### Get Translation

```yaml
method: GET
url: /api/v1/translations/{translation_id}
auth: Required
description: Retrieve a translation record and translated text.
request:
  path:
    translation_id: string
response:
  data: Translation
errors:
  - 401 unauthorized
  - 403 forbidden
  - 404 not_found
example_request: /api/v1/translations/tr_123
example_response:
  data:
    id: tr_123
    target_language: es
    translated_text: Texto traducido
```

#### Update Translation Review Status

```yaml
method: PATCH
url: /api/v1/translations/{translation_id}
auth: Required
description: Update translated text or review status.
request:
  translated_text: string
  status: string
  review_notes: string
response:
  data: Translation
errors:
  - 401 unauthorized
  - 403 forbidden
  - 404 not_found
  - 422 validation_error
example_request:
  status: approved
example_response:
  data:
    id: tr_123
    status: approved
```

### Marketing

#### List Marketing Packs

```yaml
method: GET
url: /api/v1/projects/{project_id}/marketing-packs
auth: Required
description: List marketing asset packs for a project.
request:
  query:
    book_id: string
    pack_type: string
    language: string
response:
  data: MarketingPack[]
  pagination: Pagination
errors:
  - 401 unauthorized
  - 403 forbidden
  - 404 not_found
example_request: /api/v1/projects/prj_123/marketing-packs?pack_type=kdp_listing
example_response:
  data:
    - id: mkt_123
      pack_type: kdp_listing
      language: en
```

#### Generate Marketing Pack

```yaml
method: POST
url: /api/v1/books/{book_id}/marketing-packs
auth: Required
description: Start an async job to generate marketing copy and launch assets.
request:
  pack_type: string
  language: string
  audience: string
  differentiators: string[]
  provider: string
response:
  data:
    job_id: string
    status: queued
errors:
  - 401 unauthorized
  - 403 forbidden
  - 404 not_found
  - 422 validation_error
  - 429 rate_limited
example_request:
  pack_type: kdp_listing
  language: en
  audience: Busy professionals
example_response:
  data:
    job_id: job_801
    status: queued
```

#### Get Marketing Pack

```yaml
method: GET
url: /api/v1/marketing-packs/{pack_id}
auth: Required
description: Retrieve a marketing pack.
request:
  path:
    pack_id: string
response:
  data: MarketingPack
errors:
  - 401 unauthorized
  - 403 forbidden
  - 404 not_found
example_request: /api/v1/marketing-packs/mkt_123
example_response:
  data:
    id: mkt_123
    pack_type: kdp_listing
    content:
      description: Book description
```

#### Update Marketing Pack

```yaml
method: PATCH
url: /api/v1/marketing-packs/{pack_id}
auth: Required
description: Update marketing pack content or approval status.
request:
  title: string
  content: object
  status: string
response:
  data: MarketingPack
errors:
  - 401 unauthorized
  - 403 forbidden
  - 404 not_found
  - 422 validation_error
example_request:
  status: approved
example_response:
  data:
    id: mkt_123
    status: approved
```

### Export

#### List Exports

```yaml
method: GET
url: /api/v1/projects/{project_id}/exports
auth: Required
description: List export records for a project.
request:
  query:
    book_id: string
    format: string
    status: string
response:
  data: Export[]
  pagination: Pagination
errors:
  - 401 unauthorized
  - 403 forbidden
  - 404 not_found
example_request: /api/v1/projects/prj_123/exports?format=pdf
example_response:
  data:
    - id: exp_123
      format: pdf
      status: completed
```

#### Create Export

```yaml
method: POST
url: /api/v1/books/{book_id}/exports
auth: Required
description: Start an async export job for DOCX, PDF, or EPUB.
request:
  format: string
  settings: object
  require_validation_pass: boolean
response:
  data:
    job_id: string
    export_id: string
    status: queued
errors:
  - 401 unauthorized
  - 403 forbidden
  - 404 not_found
  - 409 conflict
  - 422 validation_error
example_request:
  format: epub
  require_validation_pass: true
example_response:
  data:
    job_id: job_901
    export_id: exp_123
    status: queued
```

#### Get Export

```yaml
method: GET
url: /api/v1/exports/{export_id}
auth: Required
description: Retrieve an export record and file metadata.
request:
  path:
    export_id: string
response:
  data: Export
errors:
  - 401 unauthorized
  - 403 forbidden
  - 404 not_found
example_request: /api/v1/exports/exp_123
example_response:
  data:
    id: exp_123
    format: epub
    status: completed
    file_url: https://cdn.example.com/book.epub
```

#### Download Export

```yaml
method: GET
url: /api/v1/exports/{export_id}/download
auth: Required
description: Return a temporary download URL or stream the export file.
request:
  path:
    export_id: string
response:
  data:
    download_url: string
    expires_at: string
errors:
  - 401 unauthorized
  - 403 forbidden
  - 404 not_found
  - 409 conflict
example_request: /api/v1/exports/exp_123/download
example_response:
  data:
    download_url: https://signed.example.com/book.epub
    expires_at: "2026-07-07T13:00:00Z"
```

### Settings

#### Get User Settings

```yaml
method: GET
url: /api/v1/settings
auth: Required
description: Retrieve authenticated user settings grouped by scope.
request:
  query:
    scope: string
response:
  data:
    settings: object
errors:
  - 401 unauthorized
example_request: /api/v1/settings?scope=writing
example_response:
  data:
    settings:
      writing:
        default_tone: practical
```

#### Update User Settings

```yaml
method: PUT
url: /api/v1/settings/{scope}
auth: Required
description: Replace settings for one scope.
request:
  values: object
response:
  data:
    scope: string
    values: object
errors:
  - 401 unauthorized
  - 422 validation_error
example_request:
  values:
    default_tone: practical
example_response:
  data:
    scope: writing
    values:
      default_tone: practical
```

#### List API Keys

```yaml
method: GET
url: /api/v1/settings/api-keys
auth: Required
description: List API keys owned by the authenticated user.
request: none
response:
  data:
    - id: string
      name: string
      key_prefix: string
      scopes: string[]
      status: string
      last_used_at: string
errors:
  - 401 unauthorized
example_request: /api/v1/settings/api-keys
example_response:
  data:
    - id: key_123
      name: Zapier key
      key_prefix: aes_live_
      status: active
```

#### Create API Key

```yaml
method: POST
url: /api/v1/settings/api-keys
auth: Required
description: Create a new API key. The raw key is returned only once.
request:
  name: string
  scopes: string[]
  expires_at: string
response:
  data:
    id: string
    key: string
    key_prefix: string
errors:
  - 401 unauthorized
  - 422 validation_error
example_request:
  name: Automation key
  scopes:
    - projects:read
example_response:
  data:
    id: key_123
    key: aes_live_secret_once
    key_prefix: aes_live_
```

#### Revoke API Key

```yaml
method: DELETE
url: /api/v1/settings/api-keys/{key_id}
auth: Required
description: Revoke an API key.
request:
  path:
    key_id: string
response:
  data:
    revoked: boolean
errors:
  - 401 unauthorized
  - 403 forbidden
  - 404 not_found
example_request: /api/v1/settings/api-keys/key_123
example_response:
  data:
    revoked: true
```

### History

#### Project History

```yaml
method: GET
url: /api/v1/projects/{project_id}/history
auth: Required
description: Retrieve project activity, generation, revision, validation, and export history.
request:
  query:
    event_type: string
    page: integer
    page_size: integer
response:
  data: HistoryEvent[]
  pagination: Pagination
errors:
  - 401 unauthorized
  - 403 forbidden
  - 404 not_found
example_request: /api/v1/projects/prj_123/history?event_type=export.completed
example_response:
  data:
    - id: hist_123
      event_type: export.completed
      created_at: "2026-07-07T12:00:00Z"
```

#### Book History

```yaml
method: GET
url: /api/v1/books/{book_id}/history
auth: Required
description: Retrieve history scoped to one book.
request:
  query:
    event_type: string
    page: integer
    page_size: integer
response:
  data: HistoryEvent[]
  pagination: Pagination
errors:
  - 401 unauthorized
  - 403 forbidden
  - 404 not_found
example_request: /api/v1/books/book_123/history
example_response:
  data:
    - id: hist_124
      event_type: chapter.updated
```

#### Chapter History

```yaml
method: GET
url: /api/v1/chapters/{chapter_id}/history
auth: Required
description: Retrieve chapter-specific revisions and generation history.
request:
  query:
    page: integer
    page_size: integer
response:
  data: HistoryEvent[]
  pagination: Pagination
errors:
  - 401 unauthorized
  - 403 forbidden
  - 404 not_found
example_request: /api/v1/chapters/ch_123/history
example_response:
  data:
    - id: hist_125
      event_type: writing.generated
```

### Jobs

#### List Jobs

```yaml
method: GET
url: /api/v1/jobs
auth: Required
description: List jobs owned by the authenticated user.
request:
  query:
    project_id: string
    status: string
    job_type: string
    page: integer
    page_size: integer
response:
  data: Job[]
  pagination: Pagination
errors:
  - 401 unauthorized
example_request: /api/v1/jobs?status=running
example_response:
  data:
    - id: job_123
      type: export
      status: running
```

#### Get Job

```yaml
method: GET
url: /api/v1/jobs/{job_id}
auth: Required
description: Retrieve job status, progress, result, or error details.
request:
  path:
    job_id: string
response:
  data: Job
errors:
  - 401 unauthorized
  - 403 forbidden
  - 404 not_found
example_request: /api/v1/jobs/job_123
example_response:
  data:
    id: job_123
    status: completed
    progress: 100
```

#### Cancel Job

```yaml
method: POST
url: /api/v1/jobs/{job_id}/cancel
auth: Required
description: Request cancellation for a queued or running job.
request:
  path:
    job_id: string
response:
  data:
    id: string
    status: cancelled
errors:
  - 401 unauthorized
  - 403 forbidden
  - 404 not_found
  - 409 conflict
example_request: /api/v1/jobs/job_123/cancel
example_response:
  data:
    id: job_123
    status: cancelled
```

#### Get Job Logs

```yaml
method: GET
url: /api/v1/jobs/{job_id}/logs
auth: Required
description: Retrieve structured logs for a job.
request:
  query:
    level: string
    page: integer
    page_size: integer
response:
  data: JobLog[]
  pagination: Pagination
errors:
  - 401 unauthorized
  - 403 forbidden
  - 404 not_found
example_request: /api/v1/jobs/job_123/logs
example_response:
  data:
    - level: info
      message: Export started
```

### Notifications

#### List Notifications

```yaml
method: GET
url: /api/v1/notifications
auth: Required
description: List notifications for the authenticated user.
request:
  query:
    unread_only: boolean
    page: integer
    page_size: integer
response:
  data: Notification[]
  pagination: Pagination
errors:
  - 401 unauthorized
example_request: /api/v1/notifications?unread_only=true
example_response:
  data:
    - id: note_123
      title: Export ready
      read_at: null
```

#### Mark Notification Read

```yaml
method: POST
url: /api/v1/notifications/{notification_id}/read
auth: Required
description: Mark one notification as read.
request:
  path:
    notification_id: string
response:
  data:
    id: string
    read_at: string
errors:
  - 401 unauthorized
  - 403 forbidden
  - 404 not_found
example_request: /api/v1/notifications/note_123/read
example_response:
  data:
    id: note_123
    read_at: "2026-07-07T12:30:00Z"
```

#### Mark All Notifications Read

```yaml
method: POST
url: /api/v1/notifications/read-all
auth: Required
description: Mark all notifications for the authenticated user as read.
request: none
response:
  data:
    updated_count: integer
errors:
  - 401 unauthorized
example_request: /api/v1/notifications/read-all
example_response:
  data:
    updated_count: 8
```

#### Delete Notification

```yaml
method: DELETE
url: /api/v1/notifications/{notification_id}
auth: Required
description: Delete or hide a notification.
request:
  path:
    notification_id: string
response:
  data:
    deleted: boolean
errors:
  - 401 unauthorized
  - 403 forbidden
  - 404 not_found
example_request: /api/v1/notifications/note_123
example_response:
  data:
    deleted: true
```

## Admin Endpoint Direction

Admin endpoints should use `/api/v1/admin/*` and require administrator authorization.

Planned areas:
- User search and moderation
- Provider health
- Usage diagnostics
- Job inspection
- Audit log review

Admin endpoints are intentionally not expanded in this document because customer-facing product endpoints should stabilize first.

## OpenAPI Implementation Guidance

When implemented in FastAPI:

- Every endpoint should have request and response Pydantic schemas.
- Every route should define tags matching the module names in this document.
- Every endpoint should include summary, description, response model, and error responses.
- Async endpoints that start work should return `202 Accepted`.
- Synchronous creates should return `201 Created`.
- Reads should return `200 OK`.
- Deletes should return `200 OK` with a deletion envelope or `204 No Content`, but the API should choose one convention and use it consistently.
- Provider-specific payloads should be normalized before they reach frontend responses.
- Long-running provider operations should route through jobs rather than blocking requests.

## API Design Principles

- Keep endpoints resource-oriented.
- Keep AI provider selection explicit but abstract.
- Do not expose raw vendor responses to clients.
- Preserve traceability from outputs to inputs, provider, prompt template, and job.
- Use idempotency keys for costly create/generate/export operations.
- Prefer explicit state transitions over hidden side effects.
