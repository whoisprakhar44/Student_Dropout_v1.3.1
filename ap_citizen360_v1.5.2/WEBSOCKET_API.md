# WebSocket API Specification & Integration Guide (v1.5.2)

> **Version:** 1.5.2  
> **Protocol:** Action-Based JSON Over WebSocket  
> **Endpoints:** `ws://<host>:<port>/ws` & `ws://<host>:<port>/ws/chat`

---

## 1. Overview & Architecture

The **AP Citizen 360 (v1.5.2)** backend provides a unified, real-time WebSocket communication channel for the frontend chat interface. All interactions are driven through a single persistent WebSocket connection using **action-based message routing**.

### Key Features
- **Single WebSocket Endpoint**: Connect once to `/ws` (or `/ws/chat`) and send action payloads.
- **Execution Status Streaming**: Real-time progress updates during query execution (`generating_sql` → `formatting` → `completed`).
- **Asynchronous Non-Blocking Messages**: Operations like `ws_cancel`, `ws_history`, or `ws_ping` can be sent concurrently without blocking on active query executions.
- **Full Chat Lifecycle**: Supports query generation, session history listing, session loading, session deletion, suggestion retrieval, chart rendering, and job cancellation.

---

## 2. Complete Action Reference

### 2.1. `ws_ask` (NL2SQL Query & Execution Status Stream)

#### Client Request
```json
{
  "action": "ws_ask",
  "question": "What is the gender ratio of dropouts in Kurnool district?",
  "username": "user",
  "session_id": "sess_12345",
  "request_id": "req_998877"
}
```

#### Execution Lifecycle & Step Sequence:
1. **`step: "generating_sql"`** — Schema retrieval, few-shot matching, and LLM reasoning:
   ```json
   {
     "type": "status",
     "action": "ws_ask",
     "request_id": "req_998877",
     "session_id": "sess_12345",
     "status": "processing",
     "step": "generating_sql",
     "message": "Analyzing query intent, database schema, and synthesizing SQL query...",
     "timestamp": "2026-09-08T02:30:00.000000"
   }
   ```
2. **`step: "formatting"`** — Result extraction and chat history persistence:
   ```json
   {
     "type": "status",
     "action": "ws_ask",
     "request_id": "req_998877",
     "session_id": "sess_12345",
     "status": "processing",
     "step": "formatting",
     "message": "Formatting result rows, extracting summary, and updating session context...",
     "timestamp": "2026-09-08T02:30:01.000000"
   }
   ```
3. **`step: "completed"`** — Final status event followed by full result payload:
   ```json
   {
     "type": "result",
     "action": "ws_ask",
     "request_id": "req_998877",
     "session_id": "sess_12345",
     "status": "completed",
     "data": {
       "sql": "SELECT gender, COUNT(*) as count FROM student_dropouts WHERE district_name = 'Kurnool' GROUP BY gender;",
       "result": [
         {"gender": "Female", "count": 640},
         {"gender": "Male", "count": 590}
       ],
       "summary": "In Kurnool district, there are 640 female dropouts and 590 male dropouts.",
       "username": "user",
       "timings": {
         "total_gen_time": 1.10,
         "total_exec_time": 0.04,
         "total_time": 1.14
       }
     }
   }
   ```

---

## 3. Summary Table of Actions

| Action Name | Description | Key Payload Parameters | Return Frame Type |
|---|---|---|---|
| `ws_ask` / `ask` | Execute NL2SQL query with live status stream | `question`, `session_id`, `username`, `request_id` | `status` (stream) + `result` |
| `ws_history` / `history` | List user chat sessions | `username`, `request_id` | `result` |
| `ws_history_session` / `history_session` | Fetch message turns for session | `session_id`, `username`, `request_id` | `result` |
| `ws_delete_session` / `delete_session` | Delete a chat session | `session_id`, `username`, `request_id` | `result` |
| `ws_clear_history` / `clear_history` | Clear all sessions for user | `username`, `request_id` | `result` |
| `ws_suggestions` / `suggestions` | Fetch question exemplars & cache | `limit`, `request_id` | `result` |
| `ws_suggestions_meta` / `suggestions_meta` | Fetch suggestions cache version | `request_id` | `result` |
| `ws_chart` / `chart` | Render Vega-Lite chart to SVG | `chart_type`, `data`, `request_id` | `result` |
| `ws_cancel` / `cancel` | Cancel in-flight query | `target_request_id`, `request_id` | `result` |
| `ws_ping` / `ping` | Connection heartbeat | `request_id` | `pong` |
