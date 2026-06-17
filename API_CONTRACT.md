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

Only these application endpoints are supported.

### Health

```http
GET /health
```

Returns service status and Ollama model availability.

### Ask

```http
POST /ask
Content-Type: application/json
```

Request:

```json
{
  "question": "How many students are in the database?",
  "username": "required-username-to-scope-history",
  "request_id": "optional-custom-request-id-123",
  "session_id": "optional-session-id-for-memory",
  "thread_id": "optional-alias-for-session-id"
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
  "username": "required-username-to-scope-history"
}
```

#### Query Failure / Fallback Response

If query generation or execution fails (e.g. because of syntax errors, invalid tables/columns, or limit caps), the API will return a valid `AskResponse` with details of the failure inside the `result` block instead of throwing a HTTP error:

Response (on SQL execution failure):

```json
{
  "sql": "SELECT * FROM non_existent_table",
  "result": [
    {
      "error": "no such table: non_existent_table",
      "status": "failed"
    }
  ]
}
```

Response (on SQL generation failure):

```json
{
  "sql": "",
  "result": [
    {
      "error": "The agent did not return an executed SQL query.",
      "status": "failed"
    }
  ]
}
```

### Cancel

```http
POST /cancel
Content-Type: application/json
```

Request:

```json
{
  "request_id": "optional-custom-request-id-123"
}
```

Response:

```json
{
  "status": "success",
  "message": "Request optional-custom-request-id-123 cancellation signal sent."
}
```

Or if the request has already finished or is not active:

```json
{
  "status": "not_found",
  "message": "Request optional-custom-request-id-123 is not active or has already completed."
}
```

The `sql` value is the SQL generated and executed by the agent. The `result` value is the raw row list returned by that SQL query.

Row-returning questions use the same response shape:

```json
{
  "question": "Show 5 students"
}
```

```json
{
  "question": "Show 20 schools"
}
```

```json
{
  "question": "Show the top school"
}
```

For count queries, `result` contains one row. For list/top queries, `result` contains the requested row objects.

### History

Get history sessions:

```http
GET /history?username=test_user
```

Response:

```json
[
  {
    "id": "8a31e847-5d21-4f11-9a7c-17b5f9226e69",
    "title": "How many students are in the database?",
    "created_at": "2026-06-13T03:40:00.123456",
    "updated_at": "2026-06-13T03:41:30.987654"
  }
]
```

Get session details:

```http
GET /history/{session_id}?username=test_user
```

Response:

```json
{
  "id": "8a31e847-5d21-4f11-9a7c-17b5f9226e69",
  "title": "How many students are in the database?",
  "created_at": "2026-06-13T03:40:00.123456",
  "updated_at": "2026-06-13T03:41:30.987654",
  "messages": [
    {
      "id": "1b2c3d4e-5f6a-7b8c-9d0e-1f2a3b4c5d6e",
      "role": "user",
      "content": "How many students are in the database?",
      "sql": null,
      "result": null,
      "created_at": "2026-06-13T03:40:00.123456"
    },
    {
      "id": "9a8b7c6d-5e4f-3a2b-1c0d-ef9876543210",
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

Delete a session:

```http
DELETE /history/{session_id}?username=test_user
```

Response:

```json
{
  "status": "success",
  "message": "Session deleted successfully"
}
```

Clear all sessions:

```http
DELETE /history?username=test_user
```

Response:

```json
{
  "status": "success",
  "message": "All sessions deleted successfully"
}
```

## CORS

CORS is open for integration testing from another server:

```text
allow_origins=["*"]
```
