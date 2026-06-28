# Quick Start Guide - Curated Datamodels API

This is an API-only backend for a separately hosted frontend.

Supported application endpoints:

- `GET /health`
- `POST /ask`

`POST /ask` returns only the generated SQL query and executed result rows.

## Run

```powershell
python create_schema.py
python MCP\build_milvus_index.py
python -m uvicorn app:app --host 0.0.0.0 --port 8000
```

Ollama must be running for schema retrieval and SQL generation.

## Bruno Test

Use this request from Bruno or another server:

```http
POST http://<server-host>:8000/ask
Content-Type: application/json
```

```json
{
  "question": "How many students are in the database?"
}
```

Expected response shape:

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

Row examples for Bruno:

```json
{
  "question": "Show 20 schools"
}
```

```json
{
  "question": "Show 5 students"
}
```

```json
{
  "question": "Show the top school"
}
```

OpenAPI docs are available at:

```text
http://<server-host>:8000/docs
```
