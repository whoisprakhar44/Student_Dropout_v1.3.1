# API Contract

This project exposes one API server for a separately hosted frontend.

## Base URL

Local development:

```text
http://localhost:8000
```

Remote testing from Bruno or another server:

```text
http://<server-host>:8000
```

Interactive docs:

```http
GET /docs
```

## Endpoints

Only the following endpoints are supported.

### Health

```http
GET /health
```

Returns service status and Ollama model availability.

### Ask (Unified Endpoint)

```http
POST /ask
Content-Type: application/json
```

All interactions (executing NL-to-SQL queries, canceling queries, listing history, deleting sessions, and clearing history) are multiplexed through the `/ask` endpoint using the `action` field.

#### Fields

| Field | Type | Description |
| :--- | :--- | :--- |
| `username` | `string` | **Required.** Scopes all operations. |
| `action` | `string` | **Optional.** One of: `"ask"` (default), `"cancel"`, `"history"`, `"delete_session"`, `"clear_history"`. |
| `question` | `string` | **Required only for `"ask"` action.** The natural-language database question. |
| `request_id` | `string` | **Optional.** Custom identifier to track/cancel a running request. |
| `session_id` | `string` | **Optional.** Chat session ID for conversation memory (used in `"ask"` and `"delete_session"`). |
| `thread_id` | `string` | **Optional.** Alias for `session_id`. |

---

### 1. Action: `"ask"` (Default)

Executes a natural-language SQL query and returns a streaming response.

Request:
```json
{
  "action": "ask",
  "question": "How many students are in the database?",
  "username": "test_user",
  "request_id": "req_12345",
  "session_id": "session_abc"
}
```

Response:
```json
{
  "sql": "SELECT COUNT(*) AS total_students FROM citizen_student",
  "result": [
    {
      "total_students": 1000
    }
  ],
  "username": "test_user"
}
```

#### Failures / Fallback Response
If SQL generation or execution fails, a `failed` status will be included in the results object rather than throwing an HTTP 500 error:
```json
{
  "sql": "",
  "result": [
    {
      "error": "The agent did not return an executed SQL query.",
      "status": "failed"
    }
  ],
  "username": "test_user"
}
```

---

### 2. Action: `"cancel"`

Cancels an active running query matching the provided `request_id`.

Request:
```json
{
  "action": "cancel",
  "username": "test_user",
  "request_id": "req_12345"
}
```

Response (if active):
```json
{
  "status": "success",
  "message": "Request req_12345 cancellation signal sent."
}
```

Response (if not found or completed):
```json
{
  "status": "not_found",
  "message": "Request req_12345 is not active or has already completed."
}
```

---

### 3. Action: `"history"`

Retrieves all session histories (including message logs) scoped to the provided username.

Request:
```json
{
  "action": "history",
  "username": "test_user"
}
```

Response:
```json
[
  {
    "id": "session_abc",
    "title": "How many students are in the database?",
    "created_at": "2026-06-13T03:40:00.123456",
    "updated_at": "2026-06-13T03:41:30.987654",
    "messages": [
      {
        "id": "msg_001",
        "role": "user",
        "content": "How many students are in the database?",
        "sql": null,
        "result": null,
        "created_at": "2026-06-13T03:40:00.123456"
      },
      {
        "id": "msg_002",
        "role": "assistant",
        "content": "There are **1,000** total students in the database.",
        "sql": "SELECT COUNT(*) AS total_students FROM citizen_student",
        "result": [
          {
            "total_students": 1000
          }
        ],
        "created_at": "2026-06-13T03:40:05.654321"
      }
    ]
  }
]
```

---

### 4. Action: `"delete_session"`

Deletes a specific session history thread for a username.

Request:
```json
{
  "action": "delete_session",
  "username": "test_user",
  "session_id": "session_abc"
}
```

Response:
```json
{
  "status": "success",
  "message": "Session deleted successfully"
}
```

---

### 5. Action: `"clear_history"`

Clears all session histories associated with a username.

Request:
```json
{
  "action": "clear_history",
  "username": "test_user"
}
```

Response:
```json
{
  "status": "success",
  "message": "All sessions deleted successfully"
}
```

## CORS

CORS is open for integration testing:
```text
allow_origins=["*"]
```
