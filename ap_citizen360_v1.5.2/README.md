# Curated School Datamodel — NL2SQL Agent

FastAPI + LangGraph backend for querying the `curated_datamodels` school schema via natural language.
Includes a **modular vector-DB injection pipeline** (`pipeline.py`) that populates Milvus with
both table schemas and few-shot NL→SQL exemplars.

---

## Components

| Component | Technology |
|---|---|
| API server | FastAPI (`app.py`) |
| Agent | LangGraph (`my_agent/`) |
| Chat + embedding model | Ollama (`nomic-embed-text` + `qwen3.5`) |
| Schema retrieval | MCP `retrive_schema_rag` → Milvus Lite |
| SQL execution | MCP `execute_sql` → SQLite or Hive |
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

## Setup

> [!WARNING]
> **Milvus Lite Lock Warning**: Milvus Lite places a persistent write-lock on `milvus_schemas.db/LOCK` while the FastAPI server (`uvicorn`) or any background MCP processes are active. You **must** stop the server and any background Python subprocesses before running database initialization or few-shot injection scripts.

```bash
# 1. Create and activate virtualenv
uv venv
source .venv/bin/activate
uv pip install -r requirements.txt

# 2. Build SQLite sample database (local dev only)
python create_schema.py

# 3. Rebuild the schema and join relations index (into schema_store partition)
# (Ensure the FastAPI/uvicorn server is stopped)
python MCP/build_milvus_index.py

# 4. Inject few-shot NL→SQL pairs (into few_shot_store partition)
# (Ensure the FastAPI/uvicorn server is stopped)
python pipeline.py --config config.yaml --fewshots fewshots_combined.json

# 5. Ingest unstructured documents (PDF, DOCX, TXT into document_store partition)
# (Ensure the FastAPI/uvicorn server is stopped)
python3 MCP/ingest_documents.py

# Optional: Preview document parsing & chunking without writing to Milvus
python3 MCP/ingest_documents.py --dry_run

# 6. Start the server
python -m uvicorn app:app --host 0.0.0.0 --port 8000
```

---

## Deploying to Server

On a fresh server, after installing dependencies and pulling Ollama models, build the vector index before starting the API:

> [!IMPORTANT]
> Make sure no `uvicorn` or background python processes are running to avoid Milvus locking issues.

```bash
# First time setup / index rebuild:
python MCP/build_milvus_index.py
python pipeline.py --config config.yaml --fewshots fewshots_combined.json

# Start the server
python -m uvicorn app:app --host 0.0.0.0 --port 8000
```

> Re-run the pipeline commands any time you add new YAML schemas or few-shot examples.

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

Then start the server (inject vectors first if not already done):
```bash
# First time only (ensure uvicorn is stopped first to avoid database locking)
python MCP/build_milvus_index.py
python pipeline.py --config config.yaml --fewshots fewshots_combined.json

# Start
python -m uvicorn app:app --host 0.0.0.0 --port 8000
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
  provider: ollama          # openai | sentence_transformers | ollama
  model: nomic-embed-text   # dim=768; change dim in milvus block if you switch models
  # ollama_url is now controlled globally by OLLAMA_BASE_URL in .env

vector_db:
  provider: milvus
  milvus:
    uri: ./milvus_schemas.db   # Milvus Lite (.db file) — swap to http://host:19530 for server
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
# Ingest all PDF, DOCX, and TXT files into Milvus document_store partition
python3 MCP/ingest_documents.py

# Dry-run mode: parse and chunk without writing to Milvus
python3 MCP/ingest_documents.py --dry_run

# Custom document directory
python3 MCP/ingest_documents.py --doc_dir /path/to/documents
```

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
