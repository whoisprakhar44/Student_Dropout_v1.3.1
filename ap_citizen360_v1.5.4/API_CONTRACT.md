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
| `action` | `string` | **Optional.** One of: `"ask"` (default), `"queue_status"`, `"job_status"`, `"cancel"`, `"history"`, `"history_session"`, `"delete_session"`, `"clear_history"`, `"suggestions"`, `"suggestions_meta"`, `"chart"`, `"speech_to_text"`. |
| `question` | `string` | **Required only for `"ask"` action.** The natural-language database question. Enqueued in Valkey FIFO queue for parallel worker execution. |
| `request_id` | `string` | **Optional.** Custom identifier to track/cancel a running or queued request. |
| `session_id` | `string` | **Optional.** Chat session ID for conversation memory (used in `"ask"`, `"history_session"`, and `"delete_session"`). |
| `thread_id` | `string` | **Optional.** Alias for `session_id`. |
| `chart_type` | `string` | **Required only for `"chart"` action.** Type of chart (e.g., `"bar"`, `"line"`, `"pie"`, `"scatter"`). |
| `data` | `list[dict]` | **Required only for `"chart"` action.** The JSON result array to plot. |

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

Retrieves all session summaries (titles and creation/update times only) scoped to the provided username.

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
    "updated_at": "2026-06-13T03:41:30.987654"
  }
]
```

---

### 3b. Action: `"history_session"`

Retrieves the full message context and history details for a specific session ID scoped to a username.

Request:
```json
{
  "action": "history_session",
  "username": "test_user",
  "session_id": "session_abc"
}
```

Response:
```json
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

## 6. Action: `"chart"`

Generates an SVG chart from the provided data using Vega-Lite. 
The backend automatically determines the optimal X and Y axes using a fast LLM call.

Request:
```json
{
  "action": "chart",
  "username": "test_user",
  "chart_type": "bar",
  "data": [
    {"district_name": "Srikakulam", "total_students": 500},
    {"district_name": "Visakhapatnam", "total_students": 1200}
  ]
}
```

Response:
```json
{
  "status": "success",
  "svg": "<svg xmlns=\"http://www.w3.org/2000/svg\" ...></svg>"
}
```

---

## 7. Action: `"queue_status"`

Retrieves live metrics of the Valkey FIFO queue and parallel consumer workers.

Request:
```json
{
  "action": "queue_status",
  "username": "test_user"
}
```

Response:
```json
{
  "status": "healthy",
  "backend": "valkey",
  "concurrency_limit": 3,
  "active_workers": 1,
  "queued_jobs": 0,
  "total_enqueued": 42,
  "total_completed": 40,
  "total_failed": 2,
  "total_cancelled": 0,
  "recent_jobs": [
    {
      "job_id": "req_12345",
      "username": "test_user",
      "question": "How many students are in the database?",
      "status": "completed",
      "enqueued_at": "2026-09-02T10:15:00.123456",
      "total_time": 2.45,
      "worker_id": "worker-1"
    }
  ],
  "timestamp": "2026-09-02T10:15:05.123456"
}
```

---

## 8. Action: `"job_status"`

Checks the real-time execution status of a specific job by `request_id`.

Request:
```json
{
  "action": "job_status",
  "username": "test_user",
  "request_id": "req_12345"
}
```

Response:
```json
{
  "job_id": "req_12345",
  "question": "How many students are in the database?",
  "username": "test_user",
  "session_id": "session_abc",
  "status": "completed",
  "enqueued_at": "2026-09-02T10:15:00.123456",
  "started_at": "2026-09-02T10:15:00.150000",
  "completed_at": "2026-09-02T10:15:02.600000",
  "worker_id": "worker-1",
  "gen_time": 1.20,
  "exec_time": 0.15,
  "total_time": 2.45,
  "wait_time": 0.02,
  "result": {
    "sql": "SELECT COUNT(*) FROM citizen_student",
    "result": [{"COUNT(*)": 1000}],
    "username": "test_user"
  },
  "error": null
}
```

## CORS

CORS is open for integration testing:
```text
allow_origins=["*"]
```

