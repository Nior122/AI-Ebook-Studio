# Projects & Books API

Base path: `/api/v1`. All routes require authentication (`Bearer` token) and
enforce ownership through the service layer.

## Projects

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/projects` | List projects (search/filter/favorites). |
| GET | `/projects/recent` | Ten most recent projects. |
| POST | `/projects` | Create a project in a workspace. |
| GET | `/projects/{project_id}` | Get one project. |
| PUT / PATCH | `/projects/{project_id}` | Update overview fields. |
| DELETE | `/projects/{project_id}` | Soft-delete. |
| POST | `/projects/{project_id}/archive` | Archive. |
| POST | `/projects/{project_id}/duplicate` | Duplicate shell + settings. |
| POST | `/projects/{project_id}/favorite` | Toggle favorite. |
| GET | `/projects/{project_id}/settings` | Project AI/image settings. |
| PUT | `/projects/{project_id}/settings` | Update project settings. |

Project create body:
```json
{ "workspace_id": "uuid", "name": "My Book", "title": "My Book" }
```

## Books

A project has exactly one primary book.

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/projects/{project_id}/book` | Create / get the project's book. |
| GET | `/books/{book_id}` | Get book metadata. |
| PATCH | `/books/{book_id}` | Update book metadata. |

Book create/update fields: `title`, `description`, `language`, `target_audience`,
`writing_style`. Patch example:
```json
{ "title": "Renamed", "writing_style": "formal" }
```

## Chapters

Flat chapter API layered on the document tree. `chapter_number` is the 1-indexed
`position`; `content` is the prose body; `word_count` is derived from `content`.

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/books/{book_id}/chapters` | List chapters in order. |
| POST | `/books/{book_id}/chapters` | Create a chapter. |
| POST | `/books/{book_id}/chapters/reorder` | Reorder multiple chapters. |
| PATCH | `/chapters/{chapter_id}` | Update title/content/status/number. |
| DELETE | `/chapters/{chapter_id}` | Soft-delete + renumber. |

Create body:
```json
{ "title": "Intro", "content": "Hello world chapter." }
```

Reorder body:
```json
{ "items": [ { "chapter_id": "uuid", "chapter_number": 1 } ] }
```

## Book settings (formatting)

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/books/{book_id}/settings` | Get settings (defaults created on first read). |
| PATCH | `/books/{book_id}/settings` | Update settings. |

Defaults: `kdp_trim_size` = `6x9`, `image_aspect_ratio` = `16:9`, Georgia 11pt
body, 1.15 line spacing, centered 5-inch images. Trim sizes: `6x9`, `8x10`, `A4`,
`Letter`.

Patch example:
```json
{ "kdp_trim_size": "8x10", "body_font_size": 12.0 }
```

## Authorization
Cross-user access to any project/book/chapter/settings resource returns `403`.
Unauthenticated requests return `401`.
