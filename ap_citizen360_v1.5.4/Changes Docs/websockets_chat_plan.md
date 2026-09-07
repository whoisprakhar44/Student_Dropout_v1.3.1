# WebSocket Chat Communication Architecture Plan (ap_citizen360_v1.5.4)

## Overview
Implement an action-based, single-endpoint WebSocket architecture in `ap_citizen360_v1.5.4/app.py` (`/ws` and `/ws/chat`) supporting the full chatbot lifecycle (chat queries, history loading, session retrieval, deletion, suggestions, charts, cancellation, keepalives).
The WebSocket query pipeline integrates directly with `ValkeyQueueManager` to stream real-time planner/execution status updates (`queued` -> `guardrail_check` -> `generating_sql` -> `executing_sql` -> `completed` / `failed`) to the client, providing a foundation for future planner UI visualizations in React.

## Proposed Changes

### 1. `ap_citizen360_v1.5.4/database/valkey_queue.py`
- Enhance `ValkeyQueueManager` to support real-time progress callbacks / listeners per job:
  - Add `emit_progress(job_id, step, status, message, data=None)`
  - Add `register_progress_listener(job_id, callback)` and `unregister_progress_listener(job_id)`
  - Broadcast queue position and worker assignment status updates.

### 2. `ap_citizen360_v1.5.4/app.py`
- Update `_execute_graph_query` to invoke `queue_manager.emit_progress()` across query lifecycle stages:
  - `guardrail_check`: Validation against content policies.
  - `model_check`: Ollama status and readiness check.
  - `agent_reasoning`: LangGraph execution / SQL generation.
  - `sql_execution`: Executing generated SQL against SQLite database.
  - `formatting`: Result serialization and chat history persistence.
- Implement `@app.websocket("/ws")` and `@app.websocket("/ws/chat")`:
  - Connection manager handling message parsing, JSON serialization, and connection lifecycle.
  - Action dispatcher supporting both `ws_*` prefixed actions and standard actions:
    - `ws_ask` / `ask`: Enqueues query, subscribes to progress events, streams live planner status updates, and pushes final result.
    - `ws_history` / `history`: Returns all sessions with titles and timestamps.
    - `ws_history_session` / `history_session`: Returns full message context for a given `session_id`.
    - `ws_delete_session` / `delete_session`: Deletes a specific chat session.
    - `ws_clear_history` / `clear_history`: Clears all history for user.
    - `ws_suggestions` / `suggestions`: Returns few-shot suggestions and vector cache.
    - `ws_suggestions_meta` / `suggestions_meta`: Returns cache metadata timestamp.
    - `ws_chart` / `chart`: Generates Vega-Lite SVG charts.
    - `ws_cancel` / `cancel`: Cancels an active queued or executing query.
    - `ws_ping` / `ping`: Heartbeat pong response.
  - Graceful disconnection and error handling (non-crashing JSON error packets).

### 3. `ap_citizen360_v1.5.4/WEBSOCKET_API.md` [NEW]
- Comprehensive documentation describing:
  - WebSocket connection URL and handshake.
  - Action catalog with request/response schemas.
  - Live query status & planner step event protocol.
  - Code examples in JavaScript/React and Python.
  - Best practices for reconnects, timeouts, and state management.

### 4. `ap_citizen360_v1.5.4/test_websocket.py` [NEW]
- Automated asynchronous test suite verifying:
  - Connect and `ws_ping`.
  - `ws_suggestions` & `ws_suggestions_meta`.
  - `ws_history` & `ws_history_session`.
  - `ws_ask` query flow with step-by-step status events and final result payload.
  - `ws_chart` SVG generation.
  - `ws_cancel` and `ws_delete_session`.

## Verification Plan
1. Run syntax verification with `python -m py_compile app.py` and `database/valkey_queue.py`.
2. Start test server or execute `test_websocket.py` using FastAPI `TestClient` / `websockets` client to test every WebSocket action end-to-end.
3. Review `WEBSOCKET_API.md` for clarity and completeness.
