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

# 2. Build empty mock SQLite database (Required for syntax verification)
# This uses the new schema tables (ap_citizen360 and ap_community360)
python create_empty_schema.py

# 3. Vectorize the Schema and Join Relations (into schema_store partition)
python MCP/build_milvus_index.py

# 4. Vectorize the Few-Shot NL→SQL exemplars (into few_shot_store partition)
python pipeline.py --config config.yaml --fewshots fewshots_combined.json

# 5. Start the FastAPI backend
python -m uvicorn app:app --host 0.0.0.0 --port 8000
```

> **Prerequisite**: Ollama must be running and the `nomic-embed-text` and chat models pulled before running steps 3-5.
> ```bash
> ollama pull nomic-embed-text
> ```

---

## API Testing

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

OpenAPI docs are available at `http://<server-host>:8000/docs`.
