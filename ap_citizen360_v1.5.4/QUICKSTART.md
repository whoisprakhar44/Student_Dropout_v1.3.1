# Quick Start Guide - AP Citizen 360 & Community 360

This is an API-only backend for a separately hosted frontend that converts natural language into SQL against the unified AP Citizen 360 v1.5 datamodel.

Supported application endpoints:
- `GET /health`
- `POST /ask`

`POST /ask` returns the generated SQL query and the executed result rows.

## Fresh Server Setup

When deploying to a new server, run the following commands sequentially to build the local execution sandbox, vectorize the schemas, vectorize the few-shots, and start the API.

> [!WARNING]
> **Milvus Lite Lock Warning**: Ensure the FastAPI server (`uvicorn`) is NOT running while building the index. Stop any background Python subprocesses before running the indexing scripts to prevent database locking issues.

```bash
# 1. Create and activate virtualenv
uv venv
source .venv/bin/activate
uv pip install -r requirements.txt

# 2. Build SQLite schema database (Required for local development and syntax verification)
python create_schema.py

# 3. Vectorize Curated Schemas (into schema_store partition)
python pipeline.py --config config.yaml --yaml_dir ./schema/curated_datamodels/tables

# 4. Vectorize Few-Shot NL→SQL exemplars (into few_shot_store partition)
python pipeline.py --config config.yaml --fewshots new_fewshots.json

# 5. Start the FastAPI backend
python -m uvicorn app:app --host 0.0.0.0 --port 8000
```

> **Prerequisite**: Ollama must be running and the `nomic-embed-text` and chat models pulled before running steps 3-5.
> ```bash
> ollama pull nomic-embed-text
> ```

---

## API Testing

### 1. Execute Natural Language Query (via Valkey FIFO Queue)
Use this request from Bruno or `curl`:

```bash
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{
    "username": "tester",
    "action": "ask",
    "question": "How many class 6 students dropped out in 2025 in Anantapur?"
  }'
```

Expected response format:

```json
{
  "sql": "SELECT COUNT(*) FROM ap_citizen360.dim_student ...",
  "result": [
    {
      "COUNT(*)": 120
    }
  ],
  "username": "tester"
}
```

### 2. Check Live Queue Status & Parallel Workers
```bash
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{
    "username": "tester",
    "action": "queue_status"
  }'
```

### 3. Check Status of Specific Job
```bash
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{
    "username": "tester",
    "action": "job_status",
    "request_id": "req_12345"
  }'
```

### 4. Worker Concurrency Configuration
Configure worker pool concurrency in `.env`:
```ini
VALKEY_WORKER_CONCURRENCY=3
```

OpenAPI docs are available at `http://<server-host>:8000/docs`.
