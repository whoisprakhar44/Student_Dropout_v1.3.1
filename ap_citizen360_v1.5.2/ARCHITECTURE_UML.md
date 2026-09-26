# Conversational Query Engine — End-to-End Sequential Architecture (v1.5.2)

This document details the exact sequence of execution across all 12 stages in the **AP Citizen 360 Conversational Query Engine**.

---

## 1. Universal Mermaid Sequence Diagram

You can paste this Mermaid block directly into GitHub Markdown, Notion, Obsidian, or [Mermaid Live Editor](https://mermaid.live).

```mermaid
sequenceDiagram
    autonumber
    actor User as Citizen / Officer / User
    participant Client as Web UI / Audio Client
    participant FastAPI as FastAPI Backend (/ask, /ws)
    participant STT as Faster-Whisper STT
    participant Queue as Valkey FIFO Query Queue
    participant Agent as LangGraph Orchestrator
    participant Cache as Valkey Cache (Tier 1 & 2)
    participant LLM as Ollama LLM Engine
    participant MCP_RAG as MCP RAG Server (mcp_rag.py)
    participant Milvus as Milvus Lite Vector DB
    participant MCP_SQL as MCP SQL Server (Impala/SQLite)
    participant Impala as Impala CDP / Iceberg Warehouse

    %% ------------------------------------------------------------------------
    %% STAGE 1 & 2: INGESTION & CONCURRENT QUEUE
    %% ------------------------------------------------------------------------
    rect rgb(240, 249, 255)
    Note over User, Queue: Stage 1 & 2: Query Ingestion, Audio Transcription & FIFO Enqueue
    alt Voice Audio Query
        User->>Client: Speak Voice Query (Audio Stream)
        Client->>FastAPI: WebSocket /ws (audio_chunk)
        FastAPI->>STT: Transcribe Audio Bytes
        STT-->>FastAPI: Return Transcribed Text Query
    else Text Query
        User->>Client: Enter Question in Natural Language
        Client->>FastAPI: POST /ask (JSON payload + issuer auth)
    end
    FastAPI->>Queue: Enqueue query (valkey:query_queue)
    Queue-->>FastAPI: Job queued (Position #N)
    Queue->>Agent: Worker dequeues next task in arrival order
    end

    %% ------------------------------------------------------------------------
    %% STAGE 3: 2-TIER CACHE CHECK
    %% ------------------------------------------------------------------------
    rect rgb(236, 253, 245)
    Note over Agent, Cache: Stage 3: 2-Tier Cache Evaluation (valkey_cache_check_node)
    Agent->>Cache: Tier-1 Exact Hash Lookup (SHA256 of question)
    alt Tier-1 Exact Cache HIT
        Cache-->>Agent: Return Cached Gold SQL & Metadata
        Note over Agent, Impala: Bypass RAG and LLM Generation entirely!
    else Tier-1 Cache MISS
        Agent->>Cache: Tier-2 Semantic Similarity Search (milvus_cache.db)
        alt Tier-2 Semantic HIT (Cosine Similarity >= 0.97)
            Cache-->>Agent: Return Nearest Validated SQL & Intent
        else Tier-2 Cache MISS
            Cache-->>Agent: Full Cache MISS -> Proceed to Graph
        end
    end
    end

    %% ------------------------------------------------------------------------
    %% STAGE 4 & 5: INTENT CLASSIFICATION & DETERMINISTIC FAST PATH
    %% ------------------------------------------------------------------------
    rect rgb(254, 243, 199)
    Note over Agent, LLM: Stage 4 & 5: Intent Classification & Deterministic Search
    opt If Cache MISS
        Agent->>LLM: intent_node: Classify intent, extract entities & scope
        LLM-->>Agent: Return (intent, entities, department_scope)
        
        alt Query Type == greeting
            Agent->>Client: greeting_node: Friendly conversational greeting
        else Query Type == document_query
            Agent->>MCP_RAG: search_documents(query, top_k=5)
            MCP_RAG->>Milvus: Search document_store (PDF/DOCX embeddings)
            Milvus-->>MCP_RAG: Return relevant policy circular text chunks
            MCP_RAG-->>Agent: Return Document Passages
            Agent->>LLM: synthesize_node: Synthesize citation answer
            LLM-->>Agent: Document Policy Response
        else Query Type == data_query / hybrid
            Agent->>MCP_RAG: deterministic_search_node: search_exact_fewshot(query)
            MCP_RAG->>Milvus: Exact cosine search in few_shot_store
            Milvus-->>MCP_RAG: Return Top Exemplar + Match Score
            MCP_RAG-->>Agent: Exemplar NL2SQL pair
            
            alt Match Score >= 0.99 (Fast-Path Hit)
                Note over Agent, MCP_SQL: eval_fast_path_node: High confidence exemplar found!
                Agent->>MCP_SQL: Execute Parameterized Gold SQL directly
            else Match Score < 0.99 (Dynamic Path)
                Note over Agent, MCP_RAG: Stage 6: Dynamic Schema & Distinct Value Retrieval
                Agent->>MCP_RAG: initialize_node: retrive_schema_rag(intent, query, department)
                MCP_RAG->>Milvus: Search schema_store (Table DDLs) & few_shot_store
                Milvus-->>MCP_RAG: Top-k DDLs + Relevant SQL Exemplars
                MCP_RAG->>MCP_RAG: Inspect get_column_values (District spellings, code mappings)
                MCP_RAG-->>Agent: Enriched Schema & Exemplar Context
                
                Note over Agent, LLM: Stage 7: Self-Directed SQL Generation (llm_node)
                Agent->>LLM: Generate Impala SQL with Schema + Exemplar Constraints
                LLM-->>Agent: Tool Call: execute_sql(sql="SELECT ...")
            end
        end
    end
    end

    %% ------------------------------------------------------------------------
    %% STAGE 8 & 9: SQL EXECUTION, VERIFICATION & SELF-CORRECTION
    %% ------------------------------------------------------------------------
    rect rgb(253, 242, 248)
    Note over Agent, Impala: Stage 8 & 9: Sandboxed SQL Execution & Self-Correction
    Agent->>MCP_SQL: tool_node: execute_sql(sql_query)
    MCP_SQL->>Impala: Execute Read-Only SQL via Kerberos HiveServer2 / SQLite
    Impala-->>MCP_SQL: Return Result Rows + Column Headers (or SQL Error Trace)
    MCP_SQL-->>Agent: ToolMessage payload

    alt SQL Execution Success
        Agent->>Cache: Save successful Query + SQL in Valkey ZSET & milvus_cache.db (LRU 300)
    else SQL Execution Error (e.g., ColumnNotFound / Syntax Error)
        loop Self-Healing Correction Loop (Max 3 Retries)
            Agent->>LLM: verify_node: Error feedback + Schema context
            LLM-->>Agent: Tool Call: execute_sql(repaired_sql)
            Agent->>MCP_SQL: Execute Repaired SQL
            MCP_SQL->>Impala: Run Repaired SQL
            Impala-->>MCP_SQL: Result Rows
            MCP_SQL-->>Agent: Success
        end
    end
    end

    %% ------------------------------------------------------------------------
    %% STAGE 10, 11 & 12: SUMMARIZATION, STREAMING & AUDIT
    %% ------------------------------------------------------------------------
    rect rgb(245, 243, 255)
    Note over Agent, User: Stage 10, 11 & 12: Summarization, Visual Charting & Audit Delivery
    Agent->>LLM: summarization_node: Synthesize executive summary & chart spec
    LLM-->>Agent: Natural Language Summary + Markdown Table + Chart JSON
    Agent->>FastAPI: Final Complete Payload (Answer, SQL, Stats, Chart)
    FastAPI->>FastAPI: Write audit log to database/query_log.xlsx & save to chat_history.db
    FastAPI-->>Client: Stream Response via SSE / WebSocket
    Client-->>User: Render Interactive Visual Dashboard & Insights
    end
```

---

## 2. PlantUML Specification

```plantuml
@startuml
autonumber
actor "Citizen / Officer" as User
participant "Web UI / Audio Client" as Client
participant "FastAPI Backend" as API
participant "Faster-Whisper STT" as STT
queue "Valkey FIFO Queue" as Queue
participant "LangGraph Orchestrator" as Agent
database "Valkey 2-Tier Cache" as Cache
participant "Ollama LLM Engine" as LLM
participant "MCP RAG Server" as MCP_RAG
database "Milvus Lite Vector DB" as Milvus
participant "MCP SQL Execution" as MCP_SQL
database "Impala / Iceberg DB" as Impala

== Stage 1 & 2: Ingestion, Speech-to-Text & FIFO Enqueue ==
alt Voice Input
    User -> Client: Voice Audio Query
    Client -> API: WS /ws audio chunks
    API -> STT: Transcribe Audio Bytes
    STT --> API: Transcribed Text Query
else Text Input
    User -> Client: Type Natural Language Question
    Client -> API: POST /ask (JSON payload)
end
API -> Queue: Enqueue Query (valkey:query_queue)
Queue -> Agent: Dequeue job to worker pool

== Stage 3: 2-Tier Hybrid Cache Resolution ==
Agent -> Cache: Tier-1 Exact Hash Lookup (SHA256)
alt Tier-1 Cache HIT
    Cache --> Agent: Return Gold SQL & Metadata
else Tier-1 Cache MISS
    Agent -> Cache: Tier-2 Semantic Similarity (milvus_cache.db)
    alt Tier-2 Cache HIT (Cosine >= 0.97)
        Cache --> Agent: Return Nearest Validated SQL
    else Tier-2 Cache MISS
        Cache --> Agent: Full Cache MISS
    end
end

== Stage 4 & 5: Intent Classification & Deterministic Search ==
opt Cache MISS
    Agent -> LLM: intent_node: Classify intent & entities
    LLM --> Agent: (intent, entities, department_scope)
    
    alt Document Query (PDF/DOCX)
        Agent -> MCP_RAG: search_documents(query)
        MCP_RAG -> Milvus: Search document_store
        Milvus --> MCP_RAG: Document Passages
        MCP_RAG --> Agent: Relevant Passages
        Agent -> LLM: synthesize_node: Synthesize Citation Answer
        LLM --> Agent: Policy Answer
    else Data Query / Hybrid
        Agent -> MCP_RAG: deterministic_search_node: search_exact_fewshot
        MCP_RAG -> Milvus: Exact Vector Search in few_shot_store
        Milvus --> MCP_RAG: Top Exemplar + Score
        MCP_RAG --> Agent: Exemplar NL2SQL Pair
        
        alt Match Score >= 0.99 (Fast-Path Hit)
            Agent -> MCP_SQL: Execute Parameterized Gold SQL directly
        else Match Score < 0.99 (Dynamic Path)
            Agent -> MCP_RAG: initialize_node: retrive_schema_rag()
            MCP_RAG -> Milvus: Search schema_store & few_shot_store
            Milvus --> MCP_RAG: Top-k DDLs & Exemplars
            MCP_RAG --> Agent: Enriched Context
            Agent -> LLM: llm_node: Generate SQL with Context
            LLM --> Agent: Tool Call: execute_sql(sql)
        end
    end
end

== Stage 8 & 9: SQL Execution & Self-Healing Verification ==
Agent -> MCP_SQL: execute_sql(query)
MCP_SQL -> Impala: Run Read-Only SELECT Query
Impala --> MCP_SQL: Result Set Rows
MCP_SQL --> Agent: ToolMessage (Rows / Error)

alt Execution Error
    loop Self-Correction (Max 3 Retries)
        Agent -> LLM: verify_node: Error feedback
        LLM --> Agent: Tool Call: execute_sql(repaired_sql)
        Agent -> MCP_SQL: Run Repaired SQL
        MCP_SQL -> Impala: Execute SQL
        Impala --> MCP_SQL: Result Rows
        MCP_SQL --> Agent: Success
    end
end

Agent -> Cache: Save validated SQL to Valkey ZSET & Milvus Cache

== Stage 10, 11 & 12: Summarization, Streaming & Logging ==
Agent -> LLM: summarization_node: Synthesize Insights & Chart Spec
LLM --> Agent: Natural Summary + Markdown Table + Chart JSON
Agent -> API: Complete Response Payload
API -> API: Write audit log to query_log.xlsx & chat_history.db
API --> Client: Stream via SSE / WebSocket
Client --> User: Display Interactive Dashboard & Visuals
@enduml
```

---

## 3. Detailed Stage Breakdown

| Stage | Name | Component | Key Operations |
|---|---|---|---|
| **01** | **Ingestion & STT** | `app.py`, `Faster-Whisper` | Ingests text/audio over `/ask` or `/ws`; transcribes audio streams in real-time. |
| **02** | **FIFO Enqueue** | `Valkey` / `valkey_queue` | Non-blocking push to `valkey:query_queue`; managed N-worker pool limits concurrency. |
| **03** | **2-Tier Cache** | `valkey_cache_check_node` | Tier-1 SHA256 exact match; Tier-2 Milvus Lite cosine similarity ($\ge 0.97$). |
| **04** | **Intent & Entities** | `intent_node`, `Ollama` | Extracts intent classification, temporal/spatial entities, and YAML department scope. |
| **05** | **Fast-Path Check** | `eval_fast_path_node` | If exact few-shot similarity $\ge 0.99$, directly binds gold SQL and executes. |
| **06** | **Schema Retrieval** | `initialize_node`, `MCP RAG` | Vector similarity search in `schema_store` (DDLs) and `few_shot_store`. |
| **07** | **SQL Generation** | `llm_node`, `Qwen2.5` | Generates partition-aware read-only Impala SQL with `execute_sql` tool call. |
| **08** | **SQL Execution** | `MCP SQL Server`, `Impala` | Executes queries against Impala CDP (Kerberos SASL) or local SQLite. |
| **09** | **Self-Correction** | `verify_node` | Evaluates execution status; automatically repairs SQL errors (up to 3 retries). |
| **10** | **Document RAG** | `doc_search_node`, `synthesize_node` | Retrieves policy guidelines and circulars from `document_store`. |
| **11** | **Summarization** | `summarization_node` | Synthesizes natural executive summary, markdown tables, and chart JSON. |
| **12** | **Delivery & Audit** | `FastAPI`, `openpyxl`, `sqlite3` | SSE/WS stream to frontend; appends to `chat_history.db` & `query_log.xlsx`. |
