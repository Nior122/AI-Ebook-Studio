# Testing Checklist

## Frontend

- TypeScript passes
- Lint passes
- Responsive layout verified
- Light and dark modes verified
- Critical workflows covered by component or integration tests

## Backend

- Ruff passes
- mypy passes
- pytest passes
- API contracts have schema tests
- Repository tests cover persistence behavior

## Provider Layers

- Vendor adapters are tested with mocked HTTP responses.
- Provider errors are normalized.
- Timeouts and retries are verified.

## Deployment

- Environment variables are present.
- Migrations run successfully.
- Health checks pass.
