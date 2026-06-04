# Integration Status Report

## Current API Shape

The backend is API-only. The frontend should be hosted separately and call this server over HTTP.

Supported application endpoints:

- `GET /health`
- `POST /ask`

The old frontend/dashboard/auth/student/chat-wrapper routes are not part of the API contract.

## Ask Contract

Request:

```json
{
  "question": "How many students are in the database?"
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

Row requests use the same response shape:

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

## Run

```powershell
python create_schema.py
python MCP\build_milvus_index.py
python -m uvicorn app:app --host 0.0.0.0 --port 8000
```

## Bruno Checks

- `GET http://<server-host>:8000/health`
- `POST http://<server-host>:8000/ask`

Use `Content-Type: application/json` for `/ask`.

## Notes

- CORS is open for integration testing from another server.
- Ollama must be running and the configured chat model must be available for `/ask`.
- OpenAPI docs remain available at `/docs`.
