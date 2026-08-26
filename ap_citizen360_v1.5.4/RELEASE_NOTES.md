# Release Notes — AP Citizen 360 NL2SQL Intelligence Platform

---

## v1.5.2 — First Production Release

**Release Date:** August 2026  
**Codename:** Citizen Intelligence Platform  
**Status:** Production-Ready · Internal Release

---

## What Is This?

AP Citizen 360 v1.5.2 is the **first production release** of a conversational natural-language-to-SQL intelligence platform built for the **Andhra Pradesh Citizen 360** unified data warehouse. It enables government analysts, administrators, and domain experts to query a comprehensive 38-table citizen data model using plain English — without writing a single line of SQL.

This release represents the culmination of work across four major phases:

1. Prototyping a student dropout risk monitoring dashboard
2. Evolving the schema into a unified AP Citizen 360 datamodel
3. Building a production-grade NL2SQL agentic backend
4. Integrating Hive/Impala for enterprise database connectivity

---

## Scope & Context

The platform was originally scoped as a **Student Dropout Risk Monitoring System** — a full-stack analytics dashboard combining student-level academic and attendance data with risk scoring and AI-assisted querying. Over its development lifecycle it expanded into a general-purpose citizen intelligence layer:

- The active database grew from a school-specific prototype to a **38-table curated citizen data model** (`ap_citizen360`) spanning education, health, land, property, agriculture, vehicles, welfare, finance, demographics, and event infrastructure.
- The backend evolved from a simple SQLite-backed query interface into a **dual-mode system** supporting both local SQLite development and enterprise Kerberos-authenticated Impala/HiveServer2 production execution.
- The NL2SQL agent evolved from a basic prompt-to-query pipeline into a **multi-node LangGraph agentic system** with intent classification, RAG-assisted schema retrieval, self-correcting SQL generation, and unstructured document retrieval.

---

## Features

### 1. Natural Language to SQL — Agentic Query Engine

The core capability of this release. Ask any data question in plain English and receive verified SQL results.

- **Intent Classification**: The agent automatically classifies incoming queries as either a structured data query (SQL generation path), a policy/document query (document RAG path), or a conversational greeting (handled directly without tool execution).
- **Exact-Match Fast-Path**: Incoming data queries query the `few_shot_store` partition via `search_exact_fewshot`. If a golden question match is found (similarity $\ge 0.99$), the agent directly executes the vetted SQL and routes straight to summarization, eliminating unnecessary LLM generation rounds.
- **Semantic Schema Retrieval**: When a query requires novel generation, the agent retrieves the most relevant table schemas and join relationships using vector similarity search over Milvus. Only the schemas needed for the query are injected into the LLM context.
- **Few-Shot Augmented Generation**: The agent retrieves semantically similar NL→SQL exemplars from the `few_shot_store` partition to guide the LLM toward correct SQL patterns, especially for complex aggregations and joins.
- **Self-Correcting SQL Loop**: Successful SQL executions bypass verification and proceed straight to summarization. If execution fails, `verify_node` captures the error, formats a corrective prompt, and triggers re-retrieval or targeted rewriting.
- **Nudge Logic**: Prevents smaller Ollama models from bypassing tool calls and responding with plain text instead of executing SQL.

### 2. Dual Database Backend — SQLite & Impala/HiveServer2

A single environment flag (`HIVE_MCP_ENABLED`) switches the entire execution stack:

- **SQLite mode** (`false`): `mcp_sql_execution.py` → local SQLite database. Used for development, testing, and offline demonstrations. No external services required beyond Ollama.
- **Impala/Hive mode** (`true`): `mcp_hive_execution.py` → Kerberos-authenticated Impala queries against a live CDP Hadoop cluster. Full enterprise connectivity with session settings, connection pooling, and health checks.

When switching to Hive mode, the LLM system prompt, DDL preprocessing, and SQL dialect rules all switch together — the agent automatically uses the correct `curated_datamodels.table` prefix pattern for production queries.

### 3. MCP (Model Context Protocol) Tool Architecture

All agent–database interactions use MCP as the transport layer:

- **`retrive_schema_rag`** (`mcp_rag.py`): Vector search over `schema_store`. Returns the most relevant table schemas, foreign key joins, and reference exemplars.
- **`search_documents`** (`mcp_rag.py`): Vector search over `document_store`. Returns relevant passages from indexed PDF, DOCX, and TXT policy documents.
- **`search_exact_fewshot`** (`mcp_rag.py`): Dedicated fast-path lookup in `few_shot_store` to retrieve exact golden SQL queries.
- **`get_column_values`** (`mcp_rag.py`): Looks up distinct column values from curated metadata or table samples.
- **`get_current_date`** (`mcp_rag.py`): Resolves current timestamps, academic years (e.g. 2025-26), and financial years.
- **`execute_sql`** (`mcp_sql_execution.py` or `mcp_hive_execution.py`): Executes validated, read-only SELECT queries against SQLite or Impala and returns JSON-formatted rows.

MCP's stdio transport keeps execution servers isolated as separate processes — the agent never directly imports database drivers. Backend swapping is seamless and each execution layer is independently testable.

### 4. Three-Partition Milvus Vector Store

The Milvus collection (`schema_chunks`) uses three named partitions for clean retrieval semantics:

| Partition | Contents | Use |
|---|---|---|
| `schema_store` | Per-table YAML schemas + join relations | Schema RAG for SQL generation |
| `few_shot_store` | NL→SQL exemplar pairs | Few-shot-augmented generation & fast-path |
| `document_store` | Chunked PDF/DOCX/TXT passages | Policy and guideline RAG |

Each partition is independently buildable. The unified ingestion pipeline (`pipeline.py`) can be re-run whenever schemas or exemplars change.

### 5. AP Citizen 360 Curated Data Model — 38 Tables

The release ships with a complete curated schema for the AP Citizen 360 unified data warehouse.

**Dimension Tables (25)**

- `dim_person` — Core citizen identity (name, gender, age, caste, religion, ration card, BPL status, constituency)
- `dim_citizen_identifier` — Aadhaar, PAN, EPFO, driving licence, voter ID tracking
- `dim_driving_licence` — Driving licence details, vehicle categories, and validity dates
- `dim_family_member` — Household family composition and relationships
- `dim_household` — Household attributes (dwelling type, income category, head of household)
- `dim_health_profile` — Health data (Aarogyasri, ABHA ID, blood group, disability, ANC registrations)
- `dim_student` — Education data (APAAR ID, class, attendance, dropout reason, digital literacy)
- `dim_land` — Land holdings (survey number, hissa, acreage, irrigation type, encumbrance status)
- `dim_agriculture_profile` — Farming profile (crop types, FPO membership, PM-KISAN, soil health card)
- `dim_crop_sale` — Paddy and non-paddy sale amounts by financial year
- `dim_property` — Property registration (door number, assessment, construction type, plinth area)
- `dim_property_tax` — Property tax records (demand, arrears, payments, exemptions)
- `dim_vehicle` — Vehicle registration (make, model, fuel type, chassis, engine number)
- `dim_vehicle_compliance` — Insurance, fitness, pollution, HSRP, challan, and green tax status
- `dim_social_welfare` — Welfare scheme membership (BPL, disability, Deepam, Indiramma, PMAY)
- `dim_scheme` — Government scheme registry
- `dim_scheme_main_mapping` — Mapping of scheme aliases and department hierarchies
- `dim_department` — Government department registry
- `dim_department_client` — Department API client credentials and data access scopes
- `dim_occupation` — Employment history (sector, employer, designation, employment status)
- `dim_epfo_contribution` — EPFO provident fund contribution records
- `dim_tax_profile` — Tax records (GST, income tax, IT return status)
- `dim_utility_connection` — Electricity (SC number, DISCOM, monthly units) and gas connections
- `dim_consent` — Data sharing consent records (purposes, validity, revocation)
- `dim_secretariat` — Village and ward secretariat administration units

**Geography Dimensions (4)**

- `dim_state` — State-level demographic and economic aggregates
- `dim_district` — District-level statistics (population, literacy, land, utilities)
- `dim_mandal` — Mandal-level geo hierarchy
- `dim_village` — Village-level geo hierarchy

**Fact Tables (9)**

- `fact_benefit_transaction` — Government benefit disbursement records (scheme, amount, date)
- `fact_entitlement` — Citizen entitlement enrollment records
- `fact_scheme_disbursement` — Scheme-level disbursement aggregates by caste and beneficiary count
- `fact_population_hierarchy` — Population rollup by geo level, gender, and social category
- `fact_event_details` — Detected citizen lifecycle events and resolution tracking
- `fact_event_request_registry` — Outbound department notification requests
- `fact_event_index` — Event correlation and processing status index
- `fact_event_acknowledgement` — Department receipt and acknowledgement records
- `fact_event_status_update` — Event status update audit trail

### 6. Unstructured Document RAG

Beyond SQL schemas, the platform supports indexing and querying unstructured government documents:

- **Supported formats**: PDF (with PyMuPDF font/heading detection), DOCX (with python-docx structure extraction), plain text
- **OCR support**: Automatically extracts text embedded in images within PDFs and DOCX files using `rapidocr-onnxruntime` — no external system dependencies (Tesseract or Ghostscript) required
- **Chunking**: Text is split into overlapping passage chunks with header prefixing for context retention
- **Query routing**: `intent_node` automatically routes policy questions to the document RAG path, bypassing SQL generation entirely
- **Answer synthesis**: Retrieved passages are summarized by the LLM into a coherent response with document attribution

### 7. Session Management & Conversation Memory

- **Multi-session, multi-user**: Each user (`username`) can have multiple named sessions (`session_id`). Sessions are independent conversation threads.
- **Persistent chat history**: All sessions and messages stored in SQLite. Survives server restarts.
- **Excel query log**: All executed queries and results logged to an Excel workbook for audit and review.
- **Session operations via API**: Create, retrieve, and delete sessions; clear full user history — all through the `/ask` unified endpoint.
- **Request cancellation**: In-flight queries can be cancelled by `request_id` before they complete.

### 8. Chart Generation

The `/ask` endpoint with `action: "chart"` generates SVG charts from query result data:

- **LLM-assisted axis selection**: The LLM automatically selects the best X and Y axes based on data shape and column names
- **Chart types**: `bar`, `line`, `pie`, `scatter`
- **Backend**: Vega-Lite spec generation with `vl-convert-python` for server-side SVG rendering — no browser required
- **Integration**: Charts returned as SVG strings for direct embedding in frontend UIs

### 9. Live Speech-to-Text

A WebSocket-based real-time transcription service for voice-driven query input:

- **Model**: Faster-Whisper (configurable size: `tiny`, `base`, `small`, `medium`, `large`)
- **Protocol**: Raw PCM binary chunks streamed over WebSocket
- **Output**: Structured transcription events (text segments with timestamps and confidence)
- **Session management**: Concurrent session limiting with graceful error handling
- **Frontend guide**: Complete integration example (Angular, plain JS) in `speech_to_text/FRONTEND_LIVE_AUDIO.md`

### 10. Hive Infrastructure Validation — 7-Point Startup Check

`MCP/hive_startup_check.py` validates the full Hadoop environment before the server starts in Hive mode:

1. `JAVA_HOME` is set and accessible
2. `HADOOP_HOME` is set and `hadoop` binary is on PATH
3. `HADOOP_CONF_DIR` exists and contains core-site.xml
4. HDFS is reachable (`hdfs dfs -ls /`)
5. Valid Kerberos ticket exists (`klist`)
6. Impala TCP connectivity (port check without Impyla dependency)
7. End-to-end Impala query (`SELECT 1`) executes successfully

Failures are reported with actionable messages. The server will not start in an unhealthy environment.

### 11. Schema Drift Tracking

`schema_drift_tracker.py` compares the curated YAML schema against live production databases:

- Detects columns added, removed, or type-changed in Impala relative to YAML definitions
- Compares SQLite and Impala schemas for divergence
- Generates timestamped drift reports in `schema_drift_snapshots/`
- Prevents silent schema mismatches from breaking query generation

### 12. API Design — Unified Multiplexed Endpoint

All client interactions flow through a single `POST /ask` endpoint using an `action` discriminator. This design:

- Simplifies frontend integration (one endpoint, one auth header, one URL to whitelist)
- Keeps the API surface minimal and predictable
- Supports all operations: NL2SQL querying, history management, chart generation, request cancellation
- Returns structured JSON with `sql`, `result`, and `username` fields for consistent frontend parsing

---

## Technology Stack

| Layer | Technology | Version | Role |
|---|---|---|---|
| **Agent Framework** | LangGraph | 1.2.9 | StateGraph engine, node routing, retry loop |
| **Agent Framework** | LangChain Core | 1.5.1 | Base message schemas, prompt templates |
| **Agent Framework** | langchain-mcp-adapters | 0.3.1 | LangChain ↔ MCP integration layer |
| **Agent Framework** | langgraph-checkpoint | 4.1.1 | Persistent state checkpointing |
| **MCP Protocol** | mcp | 1.29.0 | FastMCP stdio server + client transport |
| **API Server** | FastAPI | 0.115.6 | REST endpoints, streaming, CORS |
| **API Server** | Uvicorn | 0.32.1 | ASGI server runtime |
| **Data Validation** | Pydantic | 2.13.4 | Request/response schemas, state types |
| **Data Validation** | pydantic-settings | 2.7.0 | Environment variable validation |
| **Vector Store** | pymilvus | 3.0.0 | Milvus Python client |
| **Vector Store** | milvus-lite | 3.1.1 | Embedded local vector database |
| **LLM Runtime** | Ollama | 0.6.2 | Local model serving (chat + embeddings) |
| **LLM Bindings** | langchain-ollama | 1.1.0 | LangChain-Ollama integration |
| **Embedding Model** | nomic-embed-text | 768-d | Document and schema vectorization |
| **PDF Parsing** | PyMuPDF (fitz) | 1.28.0 | PDF text extraction, heading detection |
| **DOCX Parsing** | python-docx | 1.2.0 | Word document structure extraction |
| **OCR** | rapidocr-onnxruntime | — | Embedded image text extraction (no system deps) |
| **Speech-to-Text** | Faster-Whisper | — | Real-time audio transcription |
| **Chart Rendering** | vl-convert-python | — | Vega-Lite → SVG server-side rendering |
| **Impala Driver** | impyla | 0.24.0 | HiveServer2 / Impala DB-API 2 driver |
| **Kerberos SASL** | thrift_sasl | — | GSSAPI Kerberos authentication transport |
| **Excel Logging** | openpyxl | 3.1.5 | Query audit log reader/writer |
| **Schema Format** | YAML (PyYAML) | — | Curated table and join definitions |
| **Dev Package Manager** | uv | — | Fast Python venv and dependency management |

---

## Approach & Architecture Decisions

### Why LangGraph?

LangGraph was chosen over a simple prompt-chain or vanilla ReAct loop because the query workflow has **conditional branching** (document vs. data queries), **retry loops** (SQL self-correction), and **multiple specialized nodes** (intent, routing, generation, verification, synthesis). A StateGraph gives explicit control over each transition — the agent's behavior is deterministic and auditable rather than prompt-emergent.

### Why MCP?

The Model Context Protocol decouples the agent from its execution backends. Each MCP server (`mcp_sql_execution.py`, `mcp_hive_execution.py`, `mcp_rag.py`) runs as an independent subprocess over stdio. The agent issues tool calls; the MCP layer handles transport. This means:

- SQLite and Impala backends are interchangeable without modifying the agent code
- Each execution server can be tested in isolation
- Future backends (BigQuery, Spark, etc.) can be added by writing a new MCP server

### Why Milvus with Three Partitions?

A single vector collection with partitioned namespaces was preferred over separate collections because Milvus Lite manages a single `.db` file — simpler deployment. Partition-targeted search keeps retrieval semantics strict (schema search never pulls document chunks). All three indices share the same embedding model and dimension config.

### Why Dual-Mode SQLite/Impala?

Government data systems often have a long gap between development environments and production Hadoop clusters. Maintaining strict SQLite parity for local development — with a single flag swap to Impala for production — lets the team iterate quickly without constant cluster access. The dialect-aware prompt switching and DDL preprocessing handle SQL differences transparently.

### Why YAML for Schema Definitions?

YAML was chosen over raw SQL DDLs or JSON because schema files are human-readable and reviewable by domain experts (not just engineers). The `description` and `grain` fields in each YAML embed semantic context that gets injected into the RAG index, improving retrieval relevance. Per-table YAML files make schema versioning and incremental updates surgical and diff-friendly. Join relations in separate YAML files allow cross-table join logic to evolve independently of table schemas.

### Why a Unified `/ask` Endpoint?

Multiplexing all operations through a single endpoint with an `action` discriminator simplifies frontend integration significantly — particularly for government system integrations where API contract changes require lengthy approval cycles. One endpoint, one authentication configuration, one URL to whitelist.

---

## Known Limitations (v1.5.2)

| Limitation | Notes |
|---|---|
| **Authentication** | Not implemented. CORS is open (`*`). Production deployment requires an API gateway or authentication middleware. |
| **Session storage** | Conversation history is stored in local SQLite. Multi-instance deployments require an external session store (Redis, PostgreSQL). |
| **Milvus concurrency** | Milvus Lite acquires a write-lock during indexing. The API server must be stopped before running `build_milvus_index.py` or `pipeline.py`. |
| **Ollama availability** | The server requires a running Ollama instance. If unavailable, `/health` reports degraded status and `/ask` will fail. |
| **LLM output variability** | Smaller models (< 7B parameters) may produce inconsistent SQL. The self-correction loop mitigates most failures but cannot guarantee correctness for highly complex multi-join queries. |
| **Timestamptz columns** | Impala cannot natively process `timestamptz` columns. The execution layer auto-rewrites affected columns to string casts. Additional affected columns must be registered in `MCP/hive_config.yaml`. |
| **HAVING clause dialect** | Impala/Hive do not support select-list aliases in `HAVING`. The LLM system prompt instructs against this pattern but occasional generation errors may require a retry. |
| **Rate limiting** | Not implemented. Production deployment should be fronted by a rate-limiting proxy. |
| **HTTPS** | Not configured. Production deployment requires TLS termination at the load balancer or reverse proxy. |

---

## Deployment Checklist

### Local / Development

- [ ] Ollama running with `nomic-embed-text` and chat model pulled
- [ ] `uv venv && source .venv/bin/activate && uv pip install -r requirements.txt`
- [ ] `python create_schema.py` (SQLite schema + sample data)
- [ ] `python pipeline.py --config config.yaml --yaml_dir ./schema/curated_datamodels/tables` (schema → Milvus)
- [ ] `python pipeline.py --config config.yaml --fewshots new_fewshots.json` (few-shots → Milvus)
- [ ] `HIVE_MCP_ENABLED=false` in `.env`
- [ ] `python -m uvicorn app:app --host 0.0.0.0 --port 8000`

### Production (Impala/Hive)

- [ ] Hadoop environment variables exported (`JAVA_HOME`, `HADOOP_HOME`, `HADOOP_CONF_DIR`)
- [ ] Valid Kerberos ticket obtained (`kinit`)
- [ ] `python MCP/hive_startup_check.py` passes all 7 checks
- [ ] Ollama running on production host with required models
- [ ] `python pipeline.py --config config.yaml --yaml_dir ./schema/curated_datamodels/tables` (uvicorn stopped)
- [ ] `python pipeline.py --config config.yaml --fewshots new_fewshots.json` (uvicorn stopped)
- [ ] `HIVE_MCP_ENABLED=true` in `.env`
- [ ] `python -m uvicorn app:app --host 0.0.0.0 --port 8000`

---

## Future Roadmap

| Priority | Item |
|---|---|
| High | JWT-based authentication and role-based access control |
| High | Multi-instance session store (Redis or PostgreSQL) |
| High | HTTPS / TLS configuration |
| Medium | LangGraph Studio integration for agent debugging and visualization |
| Medium | Streaming SQL results (row-by-row) over Server-Sent Events |
| Medium | Query result caching for repeated identical queries |
| Medium | Automated schema drift alerting (email / webhook) |
| Low | OpenAI / Gemini model support in addition to Ollama |
| Low | Milvus Standalone deployment for high-throughput environments |
| Low | Multi-language support for regional language query input |
| Low | Immutable audit logging with tamper-evident query history |

---

## Build Information

| Field | Value |
|---|---|
| **Version** | 1.5.2 |
| **Release Type** | First Production Release |
| **Release Date** | August 2026 |
| **Platform** | AP Citizen 360 — Government of Andhra Pradesh |
| **Backend Runtime** | Python 3.11+ |
| **Primary LLM Runtime** | Ollama (local, air-gapped compatible) |
| **Vector Database** | Milvus Lite (embedded) / Milvus Standalone (production) |
| **Database Backends** | SQLite (development) · Apache Impala / HiveServer2 (production) |
| **Agent Framework** | LangGraph 1.2.9 |
| **API Protocol** | REST (FastAPI) + MCP stdio (tool execution) + WebSocket (speech) |

---

*This document covers the AP Citizen 360 NL2SQL Intelligence Platform v1.5.2 — First Production Release.*  
*Internal release — Government of Andhra Pradesh.*
