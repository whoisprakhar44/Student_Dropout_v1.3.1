# Graph Report - ap_citizen360_v2.0  (2026-08-09)

## Corpus Check
- 54 files · ~365,669 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 520 nodes · 833 edges · 29 communities (25 shown, 4 thin omitted)
- Extraction: 94% EXTRACTED · 6% INFERRED · 0% AMBIGUOUS · INFERRED: 53 edges (avg confidence: 0.56)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `8484c2a8`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- app.py
- nodes.py
- HiveExecutor
- ✅ FINAL VERIFICATION & HANDOFF
- VectorDBClient
- mcp_rag.py
- ingest_documents.py
- manifest.json
- hive_startup_check.py
- build_milvus_index.py
- Transcriber
- Curated School Datamodel — NL2SQL Agent
- Endpoints
- Live Audio Transcription — Frontend Integration Guide
- test_generation.py
- check_llm
- mcp_sql_execution.py
- ollama_check.py
- langgraph.json
- rules/graphify.md
- workflows/graphify.md
- database/__init__.py
- mask_egress_rows
- speech_to_text/__init__.py

## God Nodes (most connected - your core abstractions)
1. `HiveExecutor` - 24 edges
2. `build_graph()` - 23 edges
3. `Transcriber` - 18 edges
4. `✅ FINAL VERIFICATION & HANDOFF` - 18 edges
5. `AgentState` - 17 edges
6. `LiveTranscriptionSession` - 15 edges
7. `VectorDBClient` - 14 edges
8. `ask()` - 13 edges
9. `TranscriptionResponse` - 12 edges
10. `run_all_checks()` - 11 edges

## Surprising Connections (you probably didn't know these)
- `main()` --calls--> `HiveExecutor`  [INFERRED]
  inspect_remote_schema.py → MCP/hive_executor.py
- `AskRequest` --uses--> `Transcriber`  [INFERRED]
  app.py → speech_to_text/transcriber.py
- `AskResponse` --uses--> `Transcriber`  [INFERRED]
  app.py → speech_to_text/transcriber.py
- `SessionSummary` --uses--> `Transcriber`  [INFERRED]
  app.py → speech_to_text/transcriber.py
- `MessageDetail` --uses--> `Transcriber`  [INFERRED]
  app.py → speech_to_text/transcriber.py

## Import Cycles
- None detected.

## Communities (29 total, 4 thin omitted)

### Community 0 - "app.py"
Cohesion: 0.06
Nodes (53): _append_excel_log(), _append_query_log(), ask(), AskRequest, AskResponse, _extract_sql_and_result(), _extract_tool_content(), get_session_messages() (+45 more)

### Community 1 - "nodes.py"
Cohesion: 0.08
Nodes (53): _get_graph(), after_tool_node(), after_verify_node(), build_graph(), main(), agent.py -------- Constructs and compiles the LangGraph agent. Graph flow:…, After llm_node: - If the LLM emitted tool calls → run the tools. - If verified…, After tool_node executes: - If the LLM called execute_sql, go to verify_node to… (+45 more)

### Community 2 - "HiveExecutor"
Cohesion: 0.07
Nodes (30): main(), format_row(), get_yaml_tables(), main(), main(), _get_engine_cfg(), HiveExecutor, _load_config() (+22 more)

### Community 3 - "✅ FINAL VERIFICATION & HANDOFF"
Cohesion: 0.05
Nodes (39): 1. ✅ Backend Integration (`app.py`), 2. ✅ Frontend Connection (`static/app.js`), 3. ✅ Database (`database/schema.db`), 4. ✅ Documentation, Academic Data: 3000 records, API Endpoints Ready, CORS: ✓ VERIFIED, Created (+31 more)

### Community 4 - "VectorDBClient"
Cohesion: 0.09
Nodes (25): build_fewshot_records(), build_schema_records(), EmbeddingGenerator, extract_embedding_text(), get_logger(), load_config(), load_fewshot_records(), load_yaml_schemas() (+17 more)

### Community 5 - "mcp_rag.py"
Cohesion: 0.12
Nodes (23): check_rate_limit(), get_cache(), get_redis(), make_cache_key(), Generate a deterministic MD5 hash key for Redis., Retrieve string value from Redis cache safely., Set string value in Redis cache safely with TTL (default 1 hr)., Sliding window rate limiter using Redis ZSET. Checks if identifier (username or… (+15 more)

### Community 6 - "ingest_documents.py"
Cohesion: 0.13
Nodes (20): build_chunks(), _build_milvus_client(), _ensure_partition(), insert_chunks(), load_config(), main(), OllamaEmbedder, _parse_docx() (+12 more)

### Community 7 - "manifest.json"
Cohesion: 0.09
Nodes (22): active_wal_number, current_seq, data_files, delta_files, build_params, field_name, index_type, metric_type (+14 more)

### Community 8 - "hive_startup_check.py"
Cohesion: 0.14
Nodes (20): check_hadoop_conf_dir(), check_hadoop_home(), check_hdfs(), check_impala_query(), check_impala_tcp(), check_java_home(), check_kerberos_ticket(), _get_engine_section() (+12 more)

### Community 9 - "build_milvus_index.py"
Cohesion: 0.17
Nodes (16): build_index(), embed_text(), load_config(), load_join_chunks(), load_table_chunks(), Build Milvus Lite schema index from schema/curated_datamodels/. Run from…, resolve_milvus_uri(), ensure_table_yaml_files() (+8 more)

### Community 10 - "Transcriber"
Cohesion: 0.14
Nodes (17): BaseSettings, get_settings(), Runtime settings for the speech-to-text API., Settings, HealthResponse, BaseModel, SegmentResponse, TranscriptionResponse (+9 more)

### Community 11 - "Curated School Datamodel — NL2SQL Agent"
Cohesion: 0.10
Nodes (20): 1. Start the Stack, 2. Initialize the Database & Vectors, Agent Flow & Self-Correction, API Endpoints, Complete Hive Setup (run in order on the server), Components, Curated School Datamodel — NL2SQL Agent, Hive Mode (Production Server) (+12 more)

### Community 12 - "Endpoints"
Cohesion: 0.12
Nodes (15): 1. Action: `"ask"` (Default), 2. Action: `"cancel"`, 3. Action: `"history"`, 3b. Action: `"history_session"`, 4. Action: `"delete_session"`, 5. Action: `"clear_history"`, 6. Action: `"chart"`, API Contract (+7 more)

### Community 13 - "Live Audio Transcription — Frontend Integration Guide"
Cohesion: 0.12
Nodes (15): 1 — Open socket and send `start`, 2 — Wait for `ready`, 3 — Stream binary PCM chunks, 4 — Receive transcription events, 5 — Stop recording, Angular Service (complete example), Audio Requirements, Backend behaviour (+7 more)

### Community 14 - "test_generation.py"
Cohesion: 0.19
Nodes (14): _extract_sql_and_result(), _extract_tool_content(), normalize_sql(), Any, Logger, Path, _QueryResult, Capture all subprocess MCP stderr (e.g. schema-retrieval) into the log file,… (+6 more)

### Community 15 - "check_llm"
Cohesion: 0.26
Nodes (12): _http_error_from_exc(), Exception, HTTPException, chat_model_name(), check_llm(), list_vllm_models(), model_is_available(), vLLM connectivity and model availability checks. (+4 more)

### Community 16 - "mcp_sql_execution.py"
Cohesion: 0.28
Nodes (8): _build_engine(), execute_sql(), tool, sql_mcp_server.py — MCP server for SQL execution. Tools: • execute_sql(query) :…, Allow ONLY read-only SELECT queries. Supports: - SELECT ... - WITH cte AS (...)…, Execute ONLY SELECT SQL queries., _resolve_sqlite_path(), _validate_query()

### Community 18 - "ollama_check.py"
Cohesion: 0.57
Nodes (6): chat_model_name(), check_ollama(), list_ollama_models(), model_is_available(), ollama_base_url(), Ollama connectivity and model availability checks.

### Community 19 - "langgraph.json"
Cohesion: 0.33
Nodes (5): dependencies, env, graphs, agent, .

### Community 23 - "mask_egress_rows"
Cohesion: 0.36
Nodes (7): get_user_role(), mask_egress_rows(), _mask_value(), Any, Mock function to get the user's role. In a real system, you would query a user…, Mask a string value according to the pattern., Masks sensitive columns in the result rows based on user role and policy.…

## Knowledge Gaps
- **88 isolated node(s):** `.`, `agent`, `env`, `active_wal_number`, `current_seq` (+83 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **4 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `build_graph()` connect `nodes.py` to `app.py`, `test_generation.py`, `mask_egress_rows`?**
  _High betweenness centrality (0.039) - this node is a cross-community bridge._
- **Why does `Transcriber` connect `Transcriber` to `app.py`?**
  _High betweenness centrality (0.020) - this node is a cross-community bridge._
- **Why does `HiveExecutor` connect `HiveExecutor` to `hive_startup_check.py`?**
  _High betweenness centrality (0.013) - this node is a cross-community bridge._
- **Are the 2 inferred relationships involving `HiveExecutor` (e.g. with `main()` and `main()`) actually correct?**
  _`HiveExecutor` has 2 INFERRED edges - model-reasoned connections that need verification._
- **Are the 12 inferred relationships involving `build_graph()` (e.g. with `after_tool_node()` and `after_verify_node()`) actually correct?**
  _`build_graph()` has 12 INFERRED edges - model-reasoned connections that need verification._
- **Are the 8 inferred relationships involving `Transcriber` (e.g. with `AskRequest` and `AskResponse`) actually correct?**
  _`Transcriber` has 8 INFERRED edges - model-reasoned connections that need verification._
- **What connects `.`, `agent`, `env` to the rest of the system?**
  _88 weakly-connected nodes found - possible documentation gaps or missing edges._