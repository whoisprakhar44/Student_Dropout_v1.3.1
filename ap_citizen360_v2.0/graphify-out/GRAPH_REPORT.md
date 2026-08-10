# Graph Report - .  (2026-08-10)

## Corpus Check
- 102 files · ~365,899 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 426 nodes · 746 edges · 24 communities (22 shown, 2 thin omitted)
- Extraction: 93% EXTRACTED · 7% INFERRED · 0% AMBIGUOUS · INFERRED: 53 edges (avg confidence: 0.56)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- Main Application API
- LangGraph Agent Workflow
- Database Inspection
- Embedding Pipeline
- Redis Caching
- Speech Config
- Milvus Vector Store
- Document Ingestion
- Hive Startup Check
- Milvus Indexing
- Test Generation
- LLM Utilities
- SQL Execution Tool
- Data Guardrails
- Ollama Integration
- LangGraph Setup
- Database Schema Gen
- Database Initialization
- Speech Init

## God Nodes (most connected - your core abstractions)
1. `HiveExecutor` - 24 edges
2. `build_graph()` - 23 edges
3. `Transcriber` - 18 edges
4. `AgentState` - 17 edges
5. `LiveTranscriptionSession` - 15 edges
6. `VectorDBClient` - 14 edges
7. `ask()` - 13 edges
8. `TranscriptionResponse` - 12 edges
9. `run_all_checks()` - 11 edges
10. `llm_node()` - 11 edges

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

## Communities (24 total, 2 thin omitted)

### Community 0 - "Main Application API"
Cohesion: 0.07
Nodes (51): _append_excel_log(), _append_query_log(), ask(), AskRequest, AskResponse, _extract_sql_and_result(), _extract_tool_content(), _get_graph() (+43 more)

### Community 1 - "LangGraph Agent Workflow"
Cohesion: 0.08
Nodes (52): after_tool_node(), after_verify_node(), build_graph(), main(), agent.py -------- Constructs and compiles the LangGraph agent. Graph flow:…, After llm_node: - If the LLM emitted tool calls → run the tools. - If verified…, After tool_node executes: - If the LLM called execute_sql, go to verify_node to…, After verify_node: - CORRECT (verified=True) → stop; the final AIMessage is… (+44 more)

### Community 2 - "Database Inspection"
Cohesion: 0.07
Nodes (30): main(), format_row(), get_yaml_tables(), main(), main(), _get_engine_cfg(), HiveExecutor, _load_config() (+22 more)

### Community 3 - "Embedding Pipeline"
Cohesion: 0.09
Nodes (25): build_fewshot_records(), build_schema_records(), EmbeddingGenerator, extract_embedding_text(), get_logger(), load_config(), load_fewshot_records(), load_yaml_schemas() (+17 more)

### Community 4 - "Redis Caching"
Cohesion: 0.12
Nodes (23): check_rate_limit(), get_cache(), get_redis(), make_cache_key(), Generate a deterministic MD5 hash key for Redis., Retrieve string value from Redis cache safely., Set string value in Redis cache safely with TTL (default 1 hr)., Sliding window rate limiter using Redis ZSET. Checks if identifier (username or… (+15 more)

### Community 5 - "Speech Config"
Cohesion: 0.14
Nodes (17): BaseSettings, get_settings(), Runtime settings for the speech-to-text API., Settings, HealthResponse, BaseModel, SegmentResponse, TranscriptionResponse (+9 more)

### Community 6 - "Milvus Vector Store"
Cohesion: 0.08
Nodes (25): active_wal_number, current_seq, data_files, delta_files, build_params, field_name, index_type, metric_type (+17 more)

### Community 7 - "Document Ingestion"
Cohesion: 0.13
Nodes (20): build_chunks(), _build_milvus_client(), _ensure_partition(), insert_chunks(), load_config(), main(), OllamaEmbedder, _parse_docx() (+12 more)

### Community 8 - "Hive Startup Check"
Cohesion: 0.14
Nodes (20): check_hadoop_conf_dir(), check_hadoop_home(), check_hdfs(), check_impala_query(), check_impala_tcp(), check_java_home(), check_kerberos_ticket(), _get_engine_section() (+12 more)

### Community 9 - "Milvus Indexing"
Cohesion: 0.17
Nodes (16): build_index(), embed_text(), load_config(), load_join_chunks(), load_table_chunks(), Build Milvus Lite schema index from schema/curated_datamodels/. Run from…, resolve_milvus_uri(), ensure_table_yaml_files() (+8 more)

### Community 10 - "Test Generation"
Cohesion: 0.19
Nodes (14): _extract_sql_and_result(), _extract_tool_content(), normalize_sql(), Any, Logger, Path, _QueryResult, Capture all subprocess MCP stderr (e.g. schema-retrieval) into the log file,… (+6 more)

### Community 11 - "LLM Utilities"
Cohesion: 0.26
Nodes (12): _http_error_from_exc(), Exception, HTTPException, chat_model_name(), check_llm(), list_vllm_models(), model_is_available(), vLLM connectivity and model availability checks. (+4 more)

### Community 12 - "SQL Execution Tool"
Cohesion: 0.28
Nodes (8): _build_engine(), execute_sql(), tool, sql_mcp_server.py — MCP server for SQL execution. Tools: • execute_sql(query) :…, Allow ONLY read-only SELECT queries. Supports: - SELECT ... - WITH cte AS (...)…, Execute ONLY SELECT SQL queries., _resolve_sqlite_path(), _validate_query()

### Community 13 - "Data Guardrails"
Cohesion: 0.36
Nodes (7): get_user_role(), mask_egress_rows(), _mask_value(), Any, Mock function to get the user's role. In a real system, you would query a user…, Mask a string value according to the pattern., Masks sensitive columns in the result rows based on user role and policy.…

### Community 14 - "Ollama Integration"
Cohesion: 0.57
Nodes (6): chat_model_name(), check_ollama(), list_ollama_models(), model_is_available(), ollama_base_url(), Ollama connectivity and model availability checks.

### Community 15 - "LangGraph Setup"
Cohesion: 0.33
Nodes (5): dependencies, env, graphs, agent, .

### Community 16 - "Database Schema Gen"
Cohesion: 0.70
Nodes (3): create_database(), _sqlite_type(), generate_synthetic_data()

## Knowledge Gaps
- **20 isolated node(s):** `.`, `agent`, `env`, `active_wal_number`, `current_seq` (+15 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **2 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `build_graph()` connect `LangGraph Agent Workflow` to `Main Application API`, `Test Generation`, `Data Guardrails`?**
  _High betweenness centrality (0.059) - this node is a cross-community bridge._
- **Why does `Transcriber` connect `Speech Config` to `Main Application API`?**
  _High betweenness centrality (0.030) - this node is a cross-community bridge._
- **Why does `HiveExecutor` connect `Database Inspection` to `Hive Startup Check`?**
  _High betweenness centrality (0.020) - this node is a cross-community bridge._
- **Are the 2 inferred relationships involving `HiveExecutor` (e.g. with `main()` and `main()`) actually correct?**
  _`HiveExecutor` has 2 INFERRED edges - model-reasoned connections that need verification._
- **Are the 12 inferred relationships involving `build_graph()` (e.g. with `after_tool_node()` and `after_verify_node()`) actually correct?**
  _`build_graph()` has 12 INFERRED edges - model-reasoned connections that need verification._
- **Are the 8 inferred relationships involving `Transcriber` (e.g. with `AskRequest` and `AskResponse`) actually correct?**
  _`Transcriber` has 8 INFERRED edges - model-reasoned connections that need verification._
- **Are the 6 inferred relationships involving `LiveTranscriptionSession` (e.g. with `AskRequest` and `AskResponse`) actually correct?**
  _`LiveTranscriptionSession` has 6 INFERRED edges - model-reasoned connections that need verification._