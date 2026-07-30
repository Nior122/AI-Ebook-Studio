# Authentication API

Base path: `/api/v1`. All protected routes require a `Authorization: Bearer
<access_token>` header.

## Endpoints

### POST `/auth/register`
Create an account. Returns the user and a token pair.

```json
{
  "email": "author@example.com",
  "password": "SecurePass123",
  "display_name": "Example Author"
}
```

Response `201`:
```json
{
  "user": { "id": "uuid", "email": "author@example.com", "display_name": "..." },
  "tokens": { "access_token": "jwt", "refresh_token": "jwt", "token_type": "bearer" }
}
```

### POST `/auth/login`
```json
{ "email": "author@example.com", "password": "SecurePass123" }
```
Returns the same token-pair shape (`200`).

### POST `/auth/refresh`
Rotate a refresh token. Body: `{ "refresh_token": "..." }`. Returns a new pair
and invalidates the old refresh token (`200`). Reuse returns `401`.

### POST `/auth/logout`
Invalidate the current refresh token (`200`).

### GET `/auth/me`
Return the current user from the bearer token. Requires auth (`200` / `401`).

## Token model
- **Access token** — short-lived JWT used as a bearer token on every protected
  route.
- **Refresh token** — longer-lived, single-use (rotated on refresh).

## Error envelope
All errors share the shape:
```json
{ "success": false, "error": { "code": "CODE", "message": "..." } }
```
Success responses include `"success": true` where applicable.
