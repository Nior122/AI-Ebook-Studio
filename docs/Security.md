# Security

## Stage 1

Authentication is designed structurally but not implemented.

## Future Requirements

- Strong password hashing if email/password auth is used.
- OAuth-ready account model.
- JWT or session strategy chosen before implementation.
- Role-based authorization for organizations and projects.
- Rate limiting for provider-backed endpoints.
- Audit events for sensitive operations.

## Secrets

Secrets must live in environment variables or platform secret stores. Never commit `.env` files.

## Provider Security

Provider keys must only be available to the backend. The frontend must never call paid AI providers directly.
