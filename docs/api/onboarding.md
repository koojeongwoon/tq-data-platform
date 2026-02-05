# Onboarding API Specification

The Onboarding module handles the transition from guest users to registered users and the collection of personalized profiling data.

## 1. Guest Registration (Unauthenticated)

### [POST] `/onboarding/registration`

Interactive flow to collect basic user info (nickname, email, password) via chat.

**Request Body**:

```json
{
  "message": "string", // User's chat message
  "session_id": "string" // Optional for first call, required for subsequent
}
```

**Response**:

- `response` (string): AI guidance/question for the next step.
- `session_id` (string): Current guest session identifier.
- `step` (string): Current state (`ask_nickname`, `ask_email`, `ask_password`, `confirm`, `complete`).
- `is_complete` (boolean): `true` when registration is finalized.
- `collected_info` (object): Map of collected fields (e.g., `{"nickname": "...", "email": "..."}`).
- `access_token` / `refresh_token`: Included only when `is_complete` is `true`.

---

## 2. Profile Collection (Authenticated)

### [POST] `/onboarding/conversation`

Collects secondary profiling data (Region, Life-cycle, Interests) from registered users.

**Authorization**: `Bearer <access_token>`

**Request Body**:

```json
{
  "message": "string", // User's response (e.g. "Seoul", "Young Adult")
  "session_id": "string" // Session ID for the collection flow
}
```

**Response**:

- `response` (string): AI acknowledgment or next question.
- `step` (string): `region` | `life_cycle` | `interests` | `complete`.
- `profile` (object): Current state of the user's profile.
- `quick_replies` (string[]): Suggestion buttons for the UI.

### [POST] `/onboarding/complete`

Explicitly finalizes the profile collection and saves data to long-term storage.

---

## 3. Session Management

### [DELETE] `/onboarding/conversation/{session_id}`

Deletes an active onboarding session if the user chooses to skip or restart.
