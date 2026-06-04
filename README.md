# Curated School Datamodel API

FastAPI backend for querying the `curated_datamodels` school data model with MCP tools. This service is API-only; the frontend should be hosted separately and call this server over HTTP.

## Components

| Component | Technology |
|-----------|------------|
| API server | FastAPI |
| Sample data | SQLite `database/schema.db` generated from curated YAML |
| Natural-language queries | LangGraph agent via `POST /ask` |
| Schema retrieval | MCP `retrive_schema_rag` + Milvus Lite |
| SQL execution | MCP `execute_sql` against SQLite or Hive |

## Supported Endpoints

Only these application endpoints are supported:

- `GET /health`
- `POST /ask`

`POST /ask` returns only the generated SQL and executed rows:

```json
{
  "sql": "SELECT ...",
  "result": []
}
```

## Setup

```bash
uv venv
source .venv/bin/activate
uv pip install -r requirements.txt
python create_schema.py
python MCP/build_milvus_index.py
python -m uvicorn app:app --host 0.0.0.0 --port 8000
```

Ollama must be running on the server for schema retrieval and SQL generation. Configure models and Hive/SQLite mode in `.env`.

## Testing From Bruno Or Another Server

Health:

```http
GET http://<server-host>:8000/health
```

Ask:

```http
POST http://<server-host>:8000/ask
Content-Type: application/json
```

Count example:

```json
{
  "question": "How many students are in the database?"
}
```

Row examples:

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

## Agent Flow

The graph starts at the LLM. The LLM decides whether to call:

- `retrive_schema_rag` for curated table DDL and join relations.
- `execute_sql` for read-only `SELECT` queries.

There is no deterministic retrieval node before every request.

## Database

`create_schema.py` parses `schema/curated_datamodels/tables/*.yaml`, creates the curated tables in SQLite, and seeds coherent sample school, student, attendance, performance, meal, scheme, and infrastructure data.
