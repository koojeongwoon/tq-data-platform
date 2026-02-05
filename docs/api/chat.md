# Chat API Specification

The Chat module provides a multi-agent orchestration layer for welfare policy discovery, calculations, and general guidance.

## 1. Core Chat Endpoints

### [POST] `/chat/conversation`

Main entry point for the persistent, multi-turn chat experience.

**Authorization**: `Bearer <access_token>`

**Request Body**:

```json
{
  "message": "string", // User query
  "session_id": "string" // Optional (creates new room if null)
}
```

**Response**:

- `response` (string): The combined answer from the specialized agents.
- `session_id` (string): The UUID of the conversation room.
- `intent` (string): Classified intent (e.g., `welfare_search`, `chitchat`, `general_question`).
- `ready_to_search` (boolean): Whether a RAG search was performed.
- `sources` (PolicyCard[]): List of policies used to generate the answer.

### [POST] `/chat/conversation/stream` (SSE)

Same as above but streams the response via Server-Sent Events.

- **Events**: `session`, `intent`, `message`, `sources`, `answer`, `profile`, `done`, `error`.

---

## 2. History & Management

### [GET] `/chat/conversations`

Lists the user's conversation rooms. Supporting pagination via `limit` and `offset`.

**Authorization**: `Bearer <access_token>`

### [GET] `/chat/conversations/{id}`

Returns full message history for a specific room.

**Authorization**: `Bearer <access_token>`

### [PATCH] `/chat/conversations/{id}`

Updates room metadata: `title`, `is_archived`, `is_pinned`.

---

## 3. Policy Interactions

### [GET] `/chat/bookmarks`

Lists all policies bookmarked by the user.

**Authorization**: `Bearer <access_token>`

### [POST] `/chat/bookmarks/{policy_id}`

Toggles bookmark status (returns `{"bookmarked": true/false}`).

**Authorization**: `Bearer <access_token>`

---

## 4. Data Models

### PolicyCard

```json
{
  "id": "string",
  "title": "string",
  "benefit_summary": "string",
  "category": "housing" | "job" | "finance" | "welfare" | "health" | "family" | "education",
  "region": "string",
  "apply_url": "string"
}
```
