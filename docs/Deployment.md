# Deployment

## Target Platforms

- Frontend: Cloudflare Pages
- Backend: Render
- Database: Neon PostgreSQL
- Repository: GitHub

## Environments

- Development
- Preview
- Staging
- Production

## Frontend Deployment

The Next.js frontend should be configured for Cloudflare Pages during the deployment stage. Environment variables exposed to the browser must use the `NEXT_PUBLIC_` prefix.

## Backend Deployment

The FastAPI backend should deploy to Render as a web service. Render environment variables should include database, auth, provider, logging, and CORS settings.

## Database Deployment

Neon branches should be used for safe preview and staging environments where practical.

## Release Rules

- Migrations must run before code requiring the new schema.
- Secrets must be set in platform dashboards, not committed.
- CI must pass before deployment.
