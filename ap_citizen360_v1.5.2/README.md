# AP Citizen 360 — Conversational NL2SQL Intelligence Platform

> **Version 1.5.2** · FastAPI · LangGraph · Milvus · Ollama · MCP · Impala/Hive

A production-grade natural-language-to-SQL backend for the **Andhra Pradesh Citizen 360** unified data platform. Converts plain-English questions into verified SQL queries against the AP Citizen 360 curated data model — spanning citizen identity, health, education, land, agriculture, property, vehicle, welfare, and financial dimensions — with full support for both local SQLite (development) and enterprise Impala/HiveServer2 (production) backends.

---

## Overview

The AP Citizen 360 NL2SQL platform is a multi-layered AI system that makes the `ap_citizen360` curated data warehouse queryable in plain language. It combines:

- **Semantic schema retrieval** — vector-similarity search over curated YAML-defined table schemas and few-shot NL→SQL exemplars stored in Milvus
- **Unstructured document RAG** — policy documents, circulars, and scheme guidelines indexed and retrievable alongside SQL schemas
- **LangGraph agentic orchestration** — intent classification, tool routing, self-correcting SQL generation, and answer synthesis in a stateful graph
- **Dual execution backends** — SQLite for local development; Kerberos-authenticated Impala/HiveServer2 for production CDP clusters
- **Live speech input** — real-time WebSocket-based audio transcription powered by Faster-Whisper for voice-driven queries

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      Frontend / API Client                       │
│                    POST /ask  ·  GET /health                     │
└─────────────────────────┬───────────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────────┐
│                   FastAPI Application (app.py)                   │
│  Session management · Request streaming · Chart generation       │
│  SQLite conversation history · Excel query log · CORS            │
└─────────────────────────┬───────────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────────┐
│              LangGraph Agent  (my_agent/)                        │
│                                                                  │
│   START → intent_node → route_node                               │
│                │                  │                              │
│           (document)           (data)                            │
│                │                  │                              │
│        doc_search_node    initialize_node                        │
│                │                  │                              │
│           tool_node ◄────────► llm_node                         │
│                │                  │                              │
│        synthesize_node      verify_node ──(retry)──► llm_node   │
│                │                  │                              │
│               END ◄──────────────┘                              │
└──────────┬──────────────────────┬───────────────────────────────┘
           │                      │
┌──────────▼──────────┐  ┌────────▼────────────────────────────┐
│   MCP RAG Server    │  │         MCP SQL Execution Server     │
│  (mcp_rag.py)       │  │  mcp_sql_execution.py  (SQLite)      │
│                     │  │  mcp_hive_execution.py (Impala)      │
│  retrive_schema_rag │  │  execute_sql (read-only SELECT)      │
│  search_documents   │  └──────────────┬──────────────────────┘
└──────────┬──────────┘                 │
           │                 ┌──────────▼──────────────┐
┌──────────▼──────────┐      │  SQLite  /  Impala CDP  │
│   Milvus Lite       │      │  ap_citizen360 schema   │
│  schema_store       │      └─────────────────────────┘
│  few_shot_store     │
│  document_store     │
└─────────────────────┘
```

---

## Data Model

The AP Citizen 360 curated data warehouse covers **26 tables** across the following domains:

| Domain | Key Tables |
|---|---|
| **Citizen Identity** | `dim_person`, `dim_citizen_identifier`, `dim_family_member` |
| **Health** | `dim_health_profile` |
| **Education** | `dim_student` |
| **Household** | `dim_household` |
| **Land & Agriculture** | `dim_land`, `dim_agriculture_profile`, `dim_crop_sale` |
| **Property & Tax** | `dim_property`, `dim_property_tax` |
| **Vehicle** | `dim_vehicle`, `dim_vehicle_compliance` |
| **Social Welfare** | `dim_social_welfare`, `dim_scheme`, `dim_consent` |
| **Employment & Finance** | `dim_occupation`, `dim_epfo_contribution`, `dim_tax_profile` |
| **Utilities** | `dim_utility_connection` |
| **Geography** | `dim_district`, `dim_mandal`, `dim_village`, `dim_state` |
| **Departments** | `dim_department`, `dim_department_client` |
| **Fact Tables** | `fact_benefit_transaction`, `fact_entitlement`, `fact_scheme_disbursement`, `fact_population_hierarchy` |

A canonical JSON schema (`citizen360_canonical_schema.json`) and curated YAML join metadata (`schema/curated_datamodels/joins/`) drive both RAG retrieval and SQL correctness.

---

## Components

| Component | Technology | Role |
|---|---|---|
| **API Server** | FastAPI 0.115.6 + Uvicorn 0.32.1 | REST endpoints, session management, streaming |
| **Agent Framework** | LangGraph 1.2.9 + LangChain Core 1.5.1 | Stateful multi-node graph, intent routing, self-correction |
| **MCP Protocol** | MCP 1.29.0 + langchain-mcp-adapters 0.3.1 | Tool transport between agent and execution servers |
| **Embedding Model** | Ollama `nomic-embed-text` (768-d) | Schema and document vectorization |
| **Chat Model** | Ollama (configurable — `qwen3.5` / `llama3.2` / others) | SQL generation and answer synthesis |
| **Vector Store** | Milvus Lite 3.1.1 / Milvus Standalone | Schema, few-shot, and document index |
| **Schema Retrieval** | `mcp_rag.py` → `retrive_schema_rag` tool | COSINE similarity search over `schema_store` |
| **Document RAG** | `mcp_rag.py` → `search_documents` tool | COSINE similarity search over `document_store` |
| **SQL Execution (Dev)** | `mcp_sql_execution.py` → SQLite | Read-only, validated SELECT execution |
| **SQL Execution (Prod)** | `mcp_hive_execution.py` → Impala via Impyla | Kerberos-authenticated Impala/HiveServer2 queries |
| **Schema Indexer** | `MCP/build_milvus_index.py` | Builds `schema_store` from YAML tables + joins |
| **Few-Shot Indexer** | `pipeline.py` | Embeds NL→SQL exemplars into `few_shot_store` |
| **Document Ingester** | `MCP/ingest_documents.py` | Parses PDF/DOCX/TXT into `document_store` (with OCR) |
| **Speech-to-Text** | `speech_to_text/` — Faster-Whisper | Live WebSocket PCM transcription |
| **Chart Generation** | `chart_generator.py` — Vega-Lite + vl-convert | LLM-assisted SVG chart rendering |
| **Schema Drift Tracker** | `schema_drift_tracker.py` | Detects schema drift between SQLite and Impala |
| **State Management** | SQLite (conversation history) | Per-user multi-session chat history |

---

## Vector Store Layout

One Milvus collection (`schema_chunks`) with **three named partitions**:

| Partition | Contents | `embedding_text` | `raw_ddl` |
|---|---|---|---|
| `schema_store` | One document per YAML table + joins | Schema prose description | DDL string |
| `few_shot_store` | NL→SQL exemplars from `fewshots_combined.json` | Natural-language question | Gold SQL query |
| `document_store` | Chunked PDF / DOCX / TXT passages | Plain chunk text | Header-prefixed chunk |

---

## Setup

> [!WARNING]
> **Milvus Lite Lock:** Milvus Lite holds a write-lock on `milvus_schemas.db/LOCK` while the server or any background MCP process is running. Always stop the server and all background subprocesses before running any indexing scripts.

### Prerequisites

- Python 3.11+
- [Ollama](https://ollama.com) running locally with required models pulled
- `uv` package manager (recommended) or `pip`

```bash
# Pull required Ollama models
ollama pull nomic-embed-text
ollama pull qwen3.5           # or your preferred chat model
```

### Installation

```bash
# 1. Create and activate virtual environment
uv venv
source .venv/bin/activate

# 2. Install dependencies
uv pip install -r requirements.txt
```

### Local Development Setup

```bash
# 3. Build empty SQLite schema database (required for SQL syntax verification)
python create_schema.py

# 4. Build schema + join-relations index (into schema_store partition)
#    Ensure uvicorn is stopped before running this
python MCP/build_milvus_index.py

# 5. Inject few-shot NL→SQL exemplars (into few_shot_store partition)
python pipeline.py --config config.yaml --fewshots fewshots_combined.json

# 6. (Optional) Ingest unstructured documents (PDF, DOCX, TXT)
python MCP/ingest_documents.py
python MCP/ingest_documents.py --dry_run     # Preview without writing
python MCP/ingest_documents.py --disable_ocr # Skip OCR for embedded images
python MCP/ingest_documents.py --doc_dir /path/to/docs

# 7. Start the server
python -m uvicorn app:app --host 0.0.0.0 --port 8000
```

### Environment Configuration (`.env`)

| Variable | Description | Default |
|---|---|---|
| `HIVE_MCP_ENABLED` | `true` for Impala/Hive, `false` for SQLite | `false` |
| `OLLAMA_BASE_URL` | Ollama server URL | `http://localhost:11434` |
| `LLM_MODEL` | Chat model name | `qwen3.5` |
| `MILVUS_URI` | Milvus connection URI | `./milvus_schemas.db` |

---

## Production Deployment (Hive/Impala Mode)

### Kerberos & Hadoop Prerequisites

> [!IMPORTANT]
> Kerberos tickets expire. Run steps 1–3 **every session** before starting the application.

```bash
# 1. Set Hadoop environment variables
export JAVA_HOME=/usr/lib/jvm/java-1.8.0-openjdk-1.8.0.492.b09-2.el9.x86_64/jre
export HADOOP_HOME=/usr/local/hadoop-3.3.6
export HADOOP_CONF_DIR=$HOME/hadoop-configuration
export PATH=$HADOOP_HOME/bin:$PATH
export CLASSPATH=$(hadoop classpath --glob)

# 2. Obtain Kerberos ticket
kinit <your-principal>

# 3. Validate all 7 environment checks (Java, Hadoop, Kerberos, HDFS, HiveServer2)
python MCP/hive_startup_check.py
```

### Enable Hive Mode

In `.env`:
```env
HIVE_MCP_ENABLED=true
```

### First-Time Server Deployment

```bash
# Ensure uvicorn is stopped, then build the index
python MCP/build_milvus_index.py
python pipeline.py --config config.yaml --fewshots fewshots_combined.json

# Start the server
python -m uvicorn app:app --host 0.0.0.0 --port 8000
```

### SQLite vs Hive/Impala — What Changes

| | SQLite (`false`) | Hive/Impala (`true`) |
|---|---|---|
| **SQL execution** | `mcp_sql_execution.py` → SQLite | `mcp_hive_execution.py` → Impala |
| **SQL dialect** | No `db.table` prefix | Requires `curated_datamodels.table` prefix |
| **DDL preprocessing** | Strips Iceberg keywords; converts types | Returns raw catalog DDL |
| **LLM system prompt** | SQLite-tuned | Hive/Impala-tuned |
| **Timestamptz handling** | Native | Auto-rewritten to string casts (KeyError 22 fix) |

### Known Production Quirk — KeyError 22 (Handled Automatically)

Impala cannot process `timestamptz` columns (`created_date`, `updated_date`). The Hive execution layer automatically rewrites SQL and casts affected columns to strings — no action needed. To add more affected columns, edit `execution.timestamptz_columns` in [`MCP/hive_config.yaml`](MCP/hive_config.yaml).

### Hive SQL Dialect — HAVING Clause

Apache Hive and Impala do **not** support select-list aliases inside `HAVING`:

```sql
-- ❌ Fails on Hive/Impala
SELECT district_name, AVG(attendance_pct) AS avg_att
FROM ... GROUP BY district_name HAVING avg_att < 55

-- ✅ Correct — repeat the expression or use a CTE
SELECT district_name, AVG(attendance_pct) AS avg_att
FROM ... GROUP BY district_name HAVING AVG(attendance_pct) < 55
```

---

## Pipeline Configuration (`config.yaml`)

```yaml
yaml_dir: ./schema/curated_datamodels/tables   # recursive YAML scan

embedding:
  provider: ollama          # openai | sentence_transformers | ollama
  model: nomic-embed-text   # dim=768
  batch_size: 32

vector_db:
  provider: milvus
  milvus:
    uri: ./milvus_schemas.db   # Milvus Lite (.db) or http://host:19530 for standalone
    collection: schema_chunks
    dim: 768
    metric_type: COSINE
```

Override `yaml_dir` at runtime without editing the config:
```bash
python pipeline.py --config config.yaml --yaml_dir ./path/to/other/yamls
```

Supported embedding providers and their dimensions:

| Provider | Model | Dimension |
|---|---|---|
| Ollama | `nomic-embed-text` | 768 |
| Ollama | `mxbai-embed-large` | 1024 |
| OpenAI | `text-embedding-3-small` | 1536 |
| Sentence Transformers | `all-MiniLM-L6-v2` | 384 |
| Sentence Transformers | `BAAI/bge-base-en-v1.5` | 768 |

---

## Agent Flow & Self-Correction

The LangGraph agent implements a stateful, multi-node graph with built-in self-correction:

```
START
  │
  ▼
intent_node         — Classifies intent: data query or document query
  │
  ▼
route_node
  ├──(document_query)──► doc_search_node ──► tool_node ──► synthesize_node ──► END
  │
  └──(data_query)──► initialize_node ──► llm_node ──► tool_node ──► verify_node
                                              ▲                           │
                                              └─────────(retry)───────────┘
                                                                          │
                                                                         END
```

### Node Responsibilities

| Node | Responsibility |
|---|---|
| `intent_node` | Classifies user intent (data query vs. document/policy query) |
| `route_node` | Dispatches to the appropriate sub-graph branch |
| `initialize_node` | Primes agent state; applies nudge logic for small models |
| `llm_node` | Calls the LLM with schema context to generate SQL |
| `tool_node` | Executes MCP tools (`retrive_schema_rag`, `execute_sql`, `search_documents`) |
| `verify_node` | Checks SQL execution outcome; loops back on error with corrective message |
| `synthesize_node` | Summarizes retrieved document passages into a natural-language answer |
| `eval_fast_path_node` | Short-circuits greeting/trivial queries to avoid unnecessary tool calls |
| `summarization_node` | Compresses long conversation context to fit the model's context window |
| `deterministic_search_node` | Attempts keyword/deterministic schema lookup before invoking the LLM |
| `doc_search_node` | Triggers document vector search for policy/guideline queries |

### Self-Correction Loop

1. `verify_node` inspects the `execute_sql` tool response for `"status": "error"`
2. On error, it formats the failed SQL and error message into a corrective `HumanMessage`
3. The agent loops back to `llm_node`, which reads the error and attempts a corrected query
4. The loop continues until execution succeeds or the retry limit is reached

---

## API Reference

Full contract: [`API_CONTRACT.md`](API_CONTRACT.md) · Interactive docs: `GET /docs`

### Base URL

```
http://localhost:8000         # local development
http://<server-host>:8000    # remote
```

### Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Liveness check with Ollama model availability |
| `POST` | `/ask` | Unified NL2SQL, history, chart, and session management endpoint |

### `/ask` — Unified Endpoint

All operations are multiplexed through `/ask` via the `action` field:

| Action | Description |
|---|---|
| `"ask"` *(default)* | Convert a natural-language question to SQL and return results |
| `"cancel"` | Cancel an in-flight request by `request_id` |
| `"history"` | List all session summaries for a username |
| `"history_session"` | Retrieve full message history for a session |
| `"delete_session"` | Delete a specific session |
| `"clear_history"` | Clear all sessions for a username |
| `"chart"` | Generate an SVG chart from query result data |

#### Quick Example

```bash
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{
    "username": "analyst",
    "action": "ask",
    "question": "How many class 6 students dropped out in 2025 in Anantapur?",
    "session_id": "session_abc"
  }'
```

```json
{
  "sql": "SELECT COUNT(*) FROM ap_citizen360.dim_student WHERE ...",
  "result": [{ "COUNT(*)": 47 }],
  "username": "analyst"
}
```

---

## Unstructured Document RAG

Place documents (PDF, DOCX, TXT) in the `documents/` directory and run:

```bash
python MCP/ingest_documents.py
```

The pipeline:
1. Parses PDFs using **PyMuPDF** (with font/heading detection)
2. Parses DOCX using **python-docx** (preserving headings and paragraphs)
3. Applies **RapidOCR** to extract text embedded in images (no system dependencies needed)
4. Chunks text into overlapping passages
5. Embeds and upserts into the `document_store` Milvus partition

At query time, `intent_node` routes policy/guideline questions to `doc_search_node`, which performs vector search and passes retrieved passages to `synthesize_node` for LLM-driven summarization.

---

## Live Speech-to-Text

The `speech_to_text/` module exposes a WebSocket endpoint for real-time audio transcription:

- **Model**: Faster-Whisper (configurable model size)
- **Input**: Raw PCM binary chunks over WebSocket
- **Output**: Streaming transcription events (segments with timestamps)
- **Sessions**: Managed concurrently with configurable limits

See [`speech_to_text/FRONTEND_LIVE_AUDIO.md`](speech_to_text/FRONTEND_LIVE_AUDIO.md) for frontend integration.

---

## Schema Drift Tracking

`schema_drift_tracker.py` compares the active schema against:
- A baseline SQLite snapshot
- The production Impala catalog

It detects added, removed, and type-changed columns, and generates drift reports to prevent silent schema mismatches from breaking queries.

---

## Project Structure

```
ap_citizen360_v1.5.2/
├── app.py                          # FastAPI application & session management
├── pipeline.py                     # Schema injection & few-shot indexing pipeline
├── config.yaml                     # Pipeline configuration
├── requirements.txt                # Python dependencies
├── langgraph.json                  # LangGraph Studio configuration
│
├── my_agent/                       # LangGraph agent
│   ├── agent.py                    # Graph definition & compilation
│   └── utils/
│       ├── nodes.py                # All graph node implementations
│       ├── tools.py                # MCP tool initialization
│       ├── state.py                # AgentState TypedDict
│       ├── chart_generator.py      # Vega-Lite SVG chart generation
│       └── ollama_check.py         # Ollama model availability check
│
├── MCP/                            # Model Context Protocol servers
│   ├── mcp_rag.py                  # Schema + document retrieval tools
│   ├── mcp_sql_execution.py        # SQLite execution server
│   ├── mcp_hive_execution.py       # Impala/HiveServer2 execution server
│   ├── hive_executor.py            # Kerberos-authenticated Impala client
│   ├── hive_startup_check.py       # 7-check Hadoop environment validator
│   ├── build_milvus_index.py       # Schema → Milvus indexer
│   ├── ingest_documents.py         # Document → Milvus ingestion
│   ├── hive_config.yaml            # Hive connection & execution config
│   └── mcp_rag.yaml                # RAG server config
│
├── schema/
│   └── curated_datamodels/
│       ├── database.yaml           # Database-level metadata
│       ├── joins/                  # Cross-table join definitions
│       └── tables/ap_citizen360/   # 26 per-table YAML schemas
│
├── speech_to_text/                 # Live transcription service
│   ├── live.py                     # WebSocket session management
│   ├── transcriber.py              # Faster-Whisper integration
│   └── schemas.py                  # Pydantic response models
│
├── citizen360_canonical_schema.json # Canonical data model (JSON Schema)
├── fewshots_combined.json          # NL→SQL training exemplars
├── schema_drift_tracker.py         # Schema change detection
├── create_schema.py                # SQLite schema creation & sample data
└── documents/                      # Unstructured documents for RAG
```

---

## Development & Testing

```bash
# Test few-shot RAG retrieval
python test_fewshot_rag.py

# Test full agent generation
python test_generation.py

# Test Impala few-shot execution
python test_fewshots_impala.py

# Inspect Impala schema
python inspect_remote_schema.py

# Inspect distinct column values
python inspect_distinct_values.py

# Check YAML schema validity
python check_yamls.py

# Schema drift detection (SQLite ↔ Impala)
python schema_drift_tracker.py
```

---

## Key Design Decisions

- **MCP (Model Context Protocol)** is used as the tool transport layer between the LangGraph agent and execution backends. This keeps SQL execution servers isolated, composable, and swappable — the agent never directly imports database drivers.
- **Intent classification** runs before any tool call, preventing unnecessary schema lookups for greetings, simple follow-ups, or document queries.
- **Dual backend support** (`HIVE_MCP_ENABLED`) lets the same agent code serve local development (SQLite) and production (Impala) without code changes — only a `.env` flag flip.
- **Retry-on-error** in `verify_node` surfaces the actual SQL error back to the LLM context, enabling dialect-aware self-correction rather than generic retry.
- **Milvus partitioning** (schema / few-shot / document) keeps retrieval semantics clean — the RAG tool targets only the relevant partition per query type.
- **Deterministic fast-path** (`deterministic_search_node`) attempts keyword-based schema lookup before invoking the full LLM generation chain, reducing latency for common queries.

---

## License

Internal / Government of Andhra Pradesh — Not for public distribution.
