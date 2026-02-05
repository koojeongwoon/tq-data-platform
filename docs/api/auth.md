# Authentication API Specification

The Auth module handles identity management and token issuance.

## 1. Core Auth

### [POST] `/auth/login` (JSON/OAuth2)

Standard login endpoint returning access and refresh tokens.

### [POST] `/auth/refresh`

Issues a new access token using a valid refresh token.

---

## 2. Security Requirements

- **Header**: `Authorization: Bearer <access_token>`
- **Cookie**: `refresh_token` (HttpOnly, Secure) for token rotation.
- **Token Expiry**:
  - Access Token: 30 minutes
  - Refresh Token: 7 days

---

## 3. User Management

### [GET] `/auth/me`

Returns the current user's profile and status.

**Authorization**: `Bearer <access_token>`

### [POST] `/auth/logout`

Invalidates all refresh tokens for the user (RTR security).

**Authorization**: `Bearer <access_token>`
