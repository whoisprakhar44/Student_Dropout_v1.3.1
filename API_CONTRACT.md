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
  "request_id": "optional-custom-request-id-123"
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

## CORS

CORS is open for integration testing from another server:

```text
allow_origins=["*"]
```
