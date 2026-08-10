# Curated School Datamodel — NL2SQL Agent

FastAPI + LangGraph backend for querying the `curated_datamodels` school schema via natural language.
Includes a **modular vector-DB injection pipeline** (`pipeline.py`) that populates Milvus with
both table schemas and few-shot NL→SQL exemplars.

---

## Components

| Component | Technology |
|---|---|
| API server | FastAPI (`app.py`) with concurrent `asyncio.Semaphore` limit |
| Agent | LangGraph (`my_agent/`) |
| Chat model | **vLLM** (`qwen3.5:0.8b-mlx`) |
| Embedding model | Ollama (`nomic-embed-text`) |
| Database / History | **PostgreSQL** (SQLAlchemy connection pool) |
| Cache & Rate Limiting | **Valkey** (Redis-compatible open-source fork — schema RAG caching + sliding window rate limit) |
| Schema retrieval | MCP `retrive_schema_rag` → Milvus (HTTP SSE transport) |
| SQL execution | MCP `execute_sql` → SQLite or Hive (HTTP SSE transport) |
| **Vector injection** | **`pipeline.py`** — schema + few-shot |

---

## Milvus Collection Layout

One collection (`schema_chunks`) with **three named partitions**:

| Partition | Contents | `embedding_text` | `raw_ddl` |
|---|---|---|---|
| `schema_store` | One doc per table YAML | Schema prose | DDL string |
| `few_shot_store` | NL→SQL exemplars | NL question | Gold SQL |
| `document_store` | Extracted PDF/DOCX/TXT chunks | Plain chunk text | Header-prefixed chunk text |

---

## Setup & Deployment (Docker Compose)

The entire backend is fully containerized. It orchestrates **PostgreSQL**, **Valkey**, **Milvus Standalone**, and the **FastAPI** backend. 

> [!IMPORTANT]
> The MCP tool servers communicate with the main API over HTTP Server-Sent Events (SSE) via internal Docker networks. Ensure **vLLM** and **Ollama** are running on your host machine (they are reached via `host.docker.internal`).

### 1. Start the Stack
Start the background services and the API servers:
```bash
docker-compose up --build -d
```
The API will be available at `http://localhost:8080`.

### 2. Initialize the Database & Vectors
Once the stack is running, populate the SQLite mock DB and Milvus vector index from your local machine.

```bash
uv venv
source .venv/bin/activate
uv pip install -r requirements.txt

# Build SQLite sample database (local mock data only)
python create_schema.py

# Rebuild the schema and join relations index (into Milvus Standalone)
MILVUS_URI="http://localhost:19530" python MCP/build_milvus_index.py

# Inject few-shot NL→SQL pairs
MILVUS_URI="http://localhost:19530" python pipeline.py --config config.yaml --fewshots fewshots_combined.json

# Ingest unstructured documents (PDF, DOCX, TXT)
MILVUS_URI="http://localhost:19530" python3 MCP/ingest_documents.py
```

### Production Controls (`.env`)
- **`VLLM_NUM_CTX=16384`**: Context window capacity natively handled by the vLLM server.
- **`RATE_LIMIT_PER_MINUTE=20`**: Valkey-backed API sliding window rate limit.
- **`MAX_CONCURRENT_QUERIES=5`**: Global semaphore limiting simultaneous LLM graph executions.

---

## Hive Mode (Production Server)

Switch from SQLite to HiveServer2 for production queries. One flag controls the entire stack — SQL execution, LLM system prompt, and DDL preprocessing all switch together.

### Complete Hive Setup (run in order on the server)

> ⚠️ Do this **every session** before starting the app. Kerberos tickets expire.

```bash
# 1. Export Hadoop env
export JAVA_HOME=/usr/lib/jvm/java-1.8.0-openjdk-1.8.0.492.b09-2.el9.x86_64/jre
export HADOOP_HOME=/usr/local/hadoop-3.3.6
export HADOOP_CONF_DIR=$HOME/hadoop-configuration
export PATH=$HADOOP_HOME/bin:$PATH
export CLASSPATH=$(hadoop classpath --glob)

# 2. Get Kerberos ticket
kinit <your-principal>

# 3. Validate everything (Java, Hadoop, Kerberos, HDFS, HiveServer2 — 7 checks)
python MCP/hive_startup_check.py

# 4. Then flip the flag and start
```

In `.env`, set:
```
HIVE_MCP_ENABLED=true
```

Then restart the Docker stack so the SQL execution server picks up the environment change:
```bash
docker-compose restart sql-server
```

### What changes when you flip `HIVE_MCP_ENABLED=true`

| | SQLite (`false`) | Hive (`true`) |
|---|---|---|
| SQL execution | `mcp_sql_execution.py` → SQLite | `mcp_hive_execution.py` → HiveServer2 |
| LLM prompt | "SQLite, no prefix" | "Hive, use `curated_datamodels.table`" |
| DDL in RAG | Stripped (Iceberg → SQLite types) | Returned as-is |

### KeyError 22 — Handled Automatically

PyHive cannot process `timestamptz` columns (`created_date`, `updated_date`). The execution layer transparently rewrites SQL and casts affected columns to strings in Python — no action needed from users or the LLM. To add more affected columns, edit `execution.timestamptz_columns` in [`MCP/hive_config.yaml`](MCP/hive_config.yaml).

---

> **Prerequisite**: Ollama must be running and `nomic-embed-text` pulled before steps 3–4:
> ```bash
> ollama pull nomic-embed-text
> ```
> Configure chat model and Hive/SQLite mode in `.env`.

---

## Pipeline Config (`config.yaml`)

```yaml
yaml_dir: ./schema/curated_datamodels/tables   # recursive YAML scan

embedding:
  provider: ollama          # ollama
  model: nomic-embed-text   # dim=768; change dim in milvus block if you switch models
  # ollama_url is controlled globally by OLLAMA_BASE_URL in .env

vector_db:
  provider: milvus
  milvus:
    uri: http://localhost:19530   # Milvus Standalone server (via Docker)
    collection: schema_chunks
    dim: 768
    metric_type: COSINE
```

Override `yaml_dir` at run time without editing the file:
```bash
python pipeline.py --config config.yaml --yaml_dir ./path/to/other/yamls
```

---

## Unstructured Document RAG (PDF, DOCX, TXT)

The pipeline supports indexing and querying unstructured documents alongside schema DDLs and few-shot pairs.

### Ingestion

Place documents in the `documents/` directory and run:

```bash
# Ingest all PDF, DOCX, and TXT files into Milvus document_store partition (includes OCR for images)
python3 MCP/ingest_documents.py

# Dry-run mode: parse and chunk without writing to Milvus
python3 MCP/ingest_documents.py --dry_run

# Disable OCR processing for embedded images
python3 MCP/ingest_documents.py --disable_ocr

# Custom document directory
python3 MCP/ingest_documents.py --doc_dir /path/to/documents
```

> **OCR Support**: Uses `rapidocr-onnxruntime` to automatically extract text embedded within images inside PDFs and DOCX files without needing external system dependencies.

### Retrieval & Synthesis Flow

1. **Intent Node**: Categorizes incoming queries. Policy/guideline/circular questions are tagged as `document_query`.
2. **Route Node**: Bypasses SQL generation for `document_query` types and routes directly to document retrieval.
3. **`search_documents` Tool**: Performs COSINE similarity vector search over `document_store` in Milvus.
4. **Synthesize Node**: LLM summarizes retrieved passages into a clear response with citations.

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Liveness check |
| `POST` | `/ask` | Natural language → SQL + result rows |

```bash
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "How many students are in the database?"}'
```

Response:
```json
{ "sql": "SELECT COUNT(*) FROM citizen_student", "result": [{"COUNT(*)": 1000}] }
```---

## Agent Flow & Self-Correction

The LangGraph architecture is designed to handle intent classification, semantic retrieval across both SQL schemas and unstructured documents, and automatic error healing:

```text
                                        START
                                          │
                                     intent_node
                                          │ (route_node)
                      ┌───────────────────┴───────────────────┐
               (document_query)                          (data_query)
                      │                                       │
               doc_search_node                         initialize_node
                      │                                       │
                      ▼                                       ▼
                  tool_node <────────────────────────────> llm_node 
                      │                                       │
                      ▼                                       ▼
               synthesize_node                           verify_node 
                      │                                       │
                      │                                       │ (RETRY loop)
                      └─────────────> END <───────────────────┘
```

### Self-Correction & SQL Error Routing
1. **Intent & Routing**: `intent_node` classifies user intent to route to either unstructured document search (`doc_search_node`) or SQL synthesis (`initialize_node`).
2. **Verification Node**: A dedicated `verify_node` in `my_agent/utils/nodes.py` intercepts SQL execution outcomes from the `tool_node` for data queries.
3. **Error Recovery**: If `execute_sql` returns a payload with `"status": "error"`, the `verify_node` captures the failure details, formats them into a corrective `HumanMessage` showing the SQL query and execution error, sets `verified=False`, and loops back to `llm_node`.
4. **Healing Loop**: The LLM reads the execution error (and retrieves schemas using RAG if needed) to generate a corrected query, preventing premature API crashes.
4. **Nudge Logic**: Prevents smaller models (e.g. `2b`) from bypassing tools or responding with plain text instead of executing SQL queries.

---

## SQLite vs Hive/Impala Mode (`.env`)

The database backend is toggled via `HIVE_MCP_ENABLED` in `.env`:

| Variable | SQLite mode (`false`) | Hive/Impala mode (`true`) |
|---|---|---|
| **SQL execution** | `mcp_sql_execution.py` → SQLite | `mcp_hive_execution.py` → Impala (via Impyla) |
| **SQL dialect** | No `db.table` prefix (e.g. `citizen_student`) | Must use `curated_datamodels.` prefix |
| **DDL preprocessing** | Strips Iceberg keywords, converts types | Returns raw catalog DDL as-is |

### SQL Dialect & Aggregate Constraints
- **SQLite HAVING Support**: SQLite allows select-list aliases inside the `HAVING` clause (e.g. `HAVING attendance_pct < 55`).
- **Hive / Impala HAVING Limitation**: Apache Hive and Impala do **not** support select-list aliases in the `HAVING` clause. 
  - *Incorrect (will fail)*: `SELECT school_name, AVG(present_flag)*100 AS att_pct FROM ... GROUP BY ... HAVING att_pct < 55`
  - *Correct (repeat computation)*: `SELECT school_name, AVG(present_flag)*100 AS att_pct FROM ... GROUP BY ... HAVING AVG(present_flag)*100 < 55` or wrap in a Common Table Expression (CTE).
