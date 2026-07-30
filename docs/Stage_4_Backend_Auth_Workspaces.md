# Stage 4 Backend: Authentication, Workspaces, And Projects

## Scope

Stage 4 implements the commercial SaaS foundation for authentication, RBAC, workspaces, and project management.

Not included:
- AI writing
- Image generation
- Ebook generation
- DOCX/PDF/EPUB export

## Authentication Flow

1. A user registers with email, password, and display name.
2. The backend validates password policy and unique email.
3. The password is hashed with bcrypt.
4. A default personal workspace is created.
5. The user is added to that workspace as `owner`.
6. The API returns a JWT access token and opaque refresh token.
7. Protected endpoints require `Authorization: Bearer <access_token>`.
8. Refresh tokens are stored hashed and rotated on use.
9. Logout revokes the supplied refresh token.

Prepared but not fully activated:
- Forgot password
- Reset password
- Email verification

## RBAC

RBAC is database-driven.

Roles:
- `owner`
- `admin`
- `editor`
- `viewer`
- `future_ai_agent`

Permissions are stored separately and attached to roles through `role_permissions`.

Workspace authorization is enforced through `workspace_members`.

## Workspace Architecture

A user can belong to many workspaces. A workspace can contain many projects.

Implemented workspace actions:
- Create
- List
- Rename/update
- Archive
- Soft delete
- Invite structure placeholder

Deletion is soft-delete based through `deleted_at`.

## Project Architecture

Projects live inside workspaces.

Implemented project actions:
- Create
- List
- Search
- Filter
- Recent projects
- Update
- Duplicate
- Archive
- Favorite/unfavorite
- Soft delete

Each project receives default project settings on creation.

## Project Settings

Project settings include:
- Book size
- Custom book size
- Margins
- Font
- Theme
- Writing language
- Image ratio
- Image style
- Default AI provider preference
- Writing style
- Export preferences
- KDP options

These are stored as structured fields and JSON where flexibility is useful.

## Database Tables

Stage 4 migration creates:
- users
- profiles
- roles
- permissions
- role_permissions
- user_roles
- workspaces
- workspace_members
- projects
- project_settings
- books
- book_versions
- folders
- activity_logs
- notifications
- sessions
- refresh_tokens
- api_keys
- jobs
- audit_logs

Every table includes UUID primary keys and timestamp/soft-delete support.

## Security Notes

- Passwords are hashed with bcrypt.
- JWT access tokens are short-lived.
- Refresh tokens are opaque, hashed at rest, and rotated.
- API keys are modeled as hashed-only values for future integrations.
- CORS remains environment-configurable.
- Security headers are applied globally.
- Rate limiting is reserved structurally for a future production hardening pass.
