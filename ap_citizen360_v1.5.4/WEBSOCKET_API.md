# WebSocket API Specification & Integration Guide

> **Version:** 1.5.4  
> **Protocol:** Action-Based JSON Over WebSocket  
> **Endpoints:** `ws://<host>:<port>/ws` & `ws://<host>:<port>/ws/chat`

---

## 1. Overview & Architecture

The **AP Citizen 360** backend provides a unified, real-time WebSocket communication channel for the frontend chat interface. Instead of maintaining separate REST endpoints for chat queries, history, suggestions, and charts, all interactions can be driven through a single persistent WebSocket connection using **action-based message routing**.

### Key Features
- **Single WebSocket Endpoint**: Connect once to `/ws` (or `/ws/chat`) and send action payloads.
- **Planner / Execution Status Streaming**: Real-time progress updates during query execution (`queued` → `worker_assigned` → `guardrail_check` → `generating_sql` → `formatting` → `completed`).
- **FIFO Queue & Parallel Workers**: Queries are scheduled through Valkey/In-Memory FIFO queue and executed across concurrent worker consumers.
- **Asynchronous Non-Blocking Messages**: Operations like `ws_cancel`, `ws_history`, or `ws_ping` can be sent concurrently without blocking on active query executions.
- **Full Chat Lifecycle**: Supports query generation, session history listing, session loading, session deletion, suggestion retrieval, chart rendering, and job cancellation.

---

## 2. Connection Details

### URLs
- Primary: `ws://localhost:8000/ws`
- Alias: `ws://localhost:8000/ws/chat`
- Production (WSS): `wss://your-domain.com/ws`

### Framing Protocol
- All client-to-server frames **must** be UTF-8 JSON text strings.
- All server-to-client responses are UTF-8 JSON text strings.

---

## 3. Message Envelope Structure

### Client Request Frame
Every frame sent from the client must be a JSON object containing an `action` identifier:

```json
{
  "action": "ws_ask",
  "request_id": "req_a1b2c3d4e5f6",
  "username": "admin_user",
  "session_id": "sess_8899aabbccdd",
  "question": "Show top 5 districts by total student dropouts in 2024"
}
```

#### Common Request Fields
| Field | Type | Required | Description |
|---|---|---|---|
| `action` | `string` | **Yes** | Action to perform (e.g. `ws_ask`, `ws_history`, `ws_suggestions`, `ws_cancel`). Pre-existing names without `ws_` prefix (e.g. `ask`, `history`) are also supported. |
| `request_id` | `string` | Optional | Unique client-generated correlation ID. Echoed back in all server responses. |
| `username` | `string` | Optional | Username scoping the chat session (defaults to `"user"`). |
| `session_id` | `string` | Optional | Conversation session UUID. |
| `thread_id` | `string` | Optional | Alias for `session_id`. |

---

### Server Response Frames
The server emits three primary types of frames:

#### 1. Real-Time Status / Planner Progress Frame (`type: "status"`)
Emitted during query execution to inform the client of the current step in the execution pipeline:

```json
{
  "type": "status",
  "action": "ws_ask",
  "request_id": "req_a1b2c3d4e5f6",
  "session_id": "sess_8899aabbccdd",
  "status": "processing",
  "step": "generating_sql",
  "message": "Analyzing query intent, database schema, and synthesizing SQL query...",
  "timestamp": "2026-09-08T02:30:00.000000",
  "data": {}
}
```

#### 2. Final Result Frame (`type: "result"`)
Emitted when an action successfully completes, fails, or is cancelled:

```json
{
  "type": "result",
  "action": "ws_ask",
  "request_id": "req_a1b2c3d4e5f6",
  "session_id": "sess_8899aabbccdd",
  "status": "completed",
  "data": {
    "sql": "SELECT district_name, SUM(dropout_count) as total_dropouts FROM student_dropouts GROUP BY district_name ORDER BY total_dropouts DESC LIMIT 5;",
    "result": [
      {"district_name": "Visakhapatnam", "total_dropouts": 1420},
      {"district_name": "Guntur", "total_dropouts": 1180}
    ],
    "summary": "Here are the top 5 districts with the highest student dropout counts.",
    "username": "admin_user",
    "timings": {
      "total_gen_time": 1.25,
      "total_exec_time": 0.08,
      "total_time": 1.33
    }
  }
}
```

#### 3. Heartbeat / Error Frames (`type: "pong"` | `type: "error"`)
```json
{
  "type": "pong",
  "action": "ws_ping",
  "request_id": "ping_01",
  "timestamp": "2026-09-08T02:30:00.000000"
}
```

---

## 4. Complete Action Reference

### 4.1. `ws_ask` (NL2SQL Query & Planner Execution Stream)
Executes a natural language query through the LangGraph AI agent and Valkey FIFO execution queue.

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
1. **`step: "queued"`** — Placed in Valkey FIFO queue:
   ```json
   {
     "type": "status",
     "action": "ws_ask",
     "request_id": "req_998877",
     "session_id": "sess_12345",
     "status": "queued",
     "step": "queued",
     "message": "Query enqueued for execution...",
     "queue_position": 1
   }
   ```
2. **`step: "worker_assigned"`** — Dequeued by parallel consumer worker:
   ```json
   {
     "type": "status",
     "action": "ws_ask",
     "request_id": "req_998877",
     "session_id": "sess_12345",
     "status": "processing",
     "step": "worker_assigned",
     "message": "Worker worker-1 assigned. Starting query processing...",
     "data": {"worker_id": "worker-1", "wait_time": 0.02}
   }
   ```
3. **`step: "guardrail_check"`** — Safety and policy evaluation:
   ```json
   {
     "type": "status",
     "action": "ws_ask",
     "request_id": "req_998877",
     "session_id": "sess_12345",
     "status": "processing",
     "step": "guardrail_check",
     "message": "Validating query safety and content guardrails..."
   }
   ```
4. **`step: "generating_sql"`** — Schema retrieval, few-shot matching, and LLM reasoning:
   ```json
   {
     "type": "status",
     "action": "ws_ask",
     "request_id": "req_998877",
     "session_id": "sess_12345",
     "status": "processing",
     "step": "generating_sql",
     "message": "Analyzing query intent, database schema, and synthesizing SQL query..."
   }
   ```
5. **`step: "formatting"`** — Result extraction and chat history persistence:
   ```json
   {
     "type": "status",
     "action": "ws_ask",
     "request_id": "req_998877",
     "session_id": "sess_12345",
     "status": "processing",
     "step": "formatting",
     "message": "Formatting result rows, extracting summary, and updating session context..."
   }
   ```
6. **`step: "completed"`** — Final status event followed by full result payload:
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

### 4.2. `ws_history` (List Chat Sessions)
Retrieves all historical chat sessions for the specified username.

#### Client Request
```json
{
  "action": "ws_history",
  "username": "user",
  "request_id": "req_hist_01"
}
```

#### Server Response
```json
{
  "type": "result",
  "action": "ws_history",
  "request_id": "req_hist_01",
  "status": "success",
  "data": [
    {
      "id": "e9b04b61-9c3f-4e0d-bca5-b82736195721",
      "title": "Dropout trends by district",
      "created_at": "2026-09-08 01:15:20",
      "updated_at": "2026-09-08 01:18:45"
    }
  ]
}
```

---

### 4.3. `ws_history_session` (Fetch Full Session Context)
Fetches all messages, generated SQLs, and query results for a specific session ID.

#### Client Request
```json
{
  "action": "ws_history_session",
  "session_id": "e9b04b61-9c3f-4e0d-bca5-b82736195721",
  "username": "user",
  "request_id": "req_sess_01"
}
```

#### Server Response
```json
{
  "type": "result",
  "action": "ws_history_session",
  "request_id": "req_sess_01",
  "session_id": "e9b04b61-9c3f-4e0d-bca5-b82736195721",
  "status": "success",
  "data": {
    "id": "e9b04b61-9c3f-4e0d-bca5-b82736195721",
    "title": "Dropout trends by district",
    "created_at": "2026-09-08 01:15:20",
    "updated_at": "2026-09-08 01:18:45",
    "messages": [
      {
        "id": "msg_1",
        "role": "user",
        "content": "Show total dropouts in Guntur",
        "sql": null,
        "result": null,
        "created_at": "2026-09-08 01:15:20"
      },
      {
        "id": "msg_2",
        "role": "assistant",
        "content": "Guntur district recorded 1,180 student dropouts.",
        "sql": "SELECT COUNT(*) FROM student_dropouts WHERE district = 'GUNTUR'",
        "result": [{"count": 1180}],
        "created_at": "2026-09-08 01:15:22"
      }
    ]
  }
}
```

---

### 4.4. `ws_delete_session` (Delete Single Session)
```json
{
  "action": "ws_delete_session",
  "session_id": "e9b04b61-9c3f-4e0d-bca5-b82736195721",
  "username": "user",
  "request_id": "req_del_01"
}
```

#### Server Response
```json
{
  "type": "result",
  "action": "ws_delete_session",
  "request_id": "req_del_01",
  "session_id": "e9b04b61-9c3f-4e0d-bca5-b82736195721",
  "status": "success",
  "message": "Session deleted successfully"
}
```

---

### 4.5. `ws_clear_history` (Clear All User History)
```json
{
  "action": "ws_clear_history",
  "username": "user",
  "request_id": "req_clr_01"
}
```

#### Server Response
```json
{
  "type": "result",
  "action": "ws_clear_history",
  "request_id": "req_clr_01",
  "status": "success",
  "message": "All sessions deleted successfully"
}
```

---

### 4.6. `ws_suggestions` (Retrieve Few-Shot Suggestions)
Retrieves the indexed question exemplars and vector embeddings for client-side matching.

```json
{
  "action": "ws_suggestions",
  "limit": 50,
  "request_id": "req_sugg_01"
}
```

#### Server Response
```json
{
  "type": "result",
  "action": "ws_suggestions",
  "request_id": "req_sugg_01",
  "status": "success",
  "data": {
    "count": 50,
    "updated_at": "2026-09-08T01:00:00.000000",
    "suggestions": [
      {
        "question": "What is the total dropout count across all schools in Anantapur?",
        "sql": "SELECT SUM(dropout_count) FROM ...",
        "embedding": [0.012, -0.043, ...]
      }
    ]
  }
}
```

---

### 4.7. `ws_suggestions_meta` (Cache Versioning Check)
```json
{
  "action": "ws_suggestions_meta",
  "request_id": "req_meta_01"
}
```

#### Server Response
```json
{
  "type": "result",
  "action": "ws_suggestions_meta",
  "request_id": "req_meta_01",
  "status": "success",
  "data": {
    "updated_at": "2026-09-08T01:00:00.000000",
    "count": 120
  }
}
```

---

### 4.8. `ws_chart` (Vega-Lite SVG Chart Generation)
Generates high-resolution SVG markup from tabular query data on the backend.

```json
{
  "action": "ws_chart",
  "chart_type": "bar",
  "data": [
    {"district": "Guntur", "dropouts": 1180},
    {"district": "Kurnool", "dropouts": 1230}
  ],
  "request_id": "req_chart_01"
}
```

#### Server Response
```json
{
  "type": "result",
  "action": "ws_chart",
  "request_id": "req_chart_01",
  "status": "success",
  "data": {
    "svg": "<svg xmlns=\"http://www.w3.org/2000/svg\" ...>...</svg>"
  }
}
```

---

### 4.9. `ws_cancel` (Cancel In-Flight Query)
Cancels a running or queued request by its `request_id`.

```json
{
  "action": "ws_cancel",
  "target_request_id": "req_998877",
  "request_id": "req_cancel_cmd"
}
```

#### Server Response
```json
{
  "type": "result",
  "action": "ws_cancel",
  "request_id": "req_cancel_cmd",
  "target_request_id": "req_998877",
  "status": "success",
  "message": "Request req_998877 cancelled successfully."
}
```

---

### 4.10. `ws_ping` (Heartbeat)
```json
{
  "action": "ws_ping",
  "request_id": "ping_1"
}
```

#### Server Response
```json
{
  "type": "pong",
  "action": "ws_ping",
  "request_id": "ping_1",
  "timestamp": "2026-09-08T02:30:15.000000"
}
```

---

## 5. React / JavaScript Implementation Guide

Below is a production-ready React custom hook `useChatWebSocket` demonstrating automatic reconnection, action dispatching, and real-time execution step tracking:

```javascript
import { useEffect, useRef, useState, useCallback } from "react";

export function useChatWebSocket(wsUrl = "ws://localhost:8000/ws") {
  const wsRef = useRef(null);
  const [isConnected, setIsConnected] = useState(false);
  const [currentStep, setCurrentStep] = useState(null); // Live planner step
  const [lastResult, setLastResult] = useState(null);
  const pendingCallbacks = useRef(new Map());

  // Connect on mount
  useEffect(() => {
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      console.log("WebSocket connected.");
      setIsConnected(true);
    };

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);

        // 1. Live status / planner event
        if (msg.type === "status") {
          setCurrentStep({
            step: msg.step,
            message: msg.message,
            status: msg.status,
            requestId: msg.request_id,
            data: msg.data
          });
        }

        // 2. Final result event
        if (msg.type === "result") {
          setLastResult(msg);
          setCurrentStep(null); // Clear active step
          
          const cb = pendingCallbacks.current.get(msg.request_id);
          if (cb) {
            cb(msg);
            pendingCallbacks.current.delete(msg.request_id);
          }
        }
      } catch (err) {
        console.error("Failed to parse WS message", err);
      }
    };

    ws.onclose = () => {
      console.log("WebSocket disconnected.");
      setIsConnected(false);
    };

    return () => {
      ws.close();
    };
  }, [wsUrl]);

  // Send action helper with Promise resolution
  const sendAction = useCallback((action, payload = {}) => {
    return new Promise((resolve, reject) => {
      if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
        return reject(new Error("WebSocket is not connected"));
      }

      const requestId = payload.request_id || `req_${Date.now()}`;
      const msg = { action, ...payload, request_id: requestId };

      pendingCallbacks.current.set(requestId, resolve);
      wsRef.current.send(JSON.stringify(msg));
    });
  }, []);

  return {
    isConnected,
    currentStep,
    lastResult,
    sendAction,
    ask: (question, session_id, username = "user") => 
      sendAction("ws_ask", { question, session_id, username }),
    fetchHistory: (username = "user") => 
      sendAction("ws_history", { username }),
    fetchSession: (session_id, username = "user") => 
      sendAction("ws_history_session", { session_id, username }),
    deleteSession: (session_id, username = "user") => 
      sendAction("ws_delete_session", { session_id, username }),
    cancelQuery: (target_request_id) => 
      sendAction("ws_cancel", { target_request_id }),
    fetchSuggestions: (limit = 50) => 
      sendAction("ws_suggestions", { limit }),
  };
}
```

---

## 6. Python Asynchronous Client Example

```python
import asyncio
import json
import websockets

async def chat_session_demo():
    uri = "ws://localhost:8000/ws"
    async with websockets.connect(uri) as ws:
        # 1. Ping
        await ws.send(json.dumps({"action": "ws_ping"}))
        print("Pong:", await ws.recv())

        # 2. Ask Question
        query_msg = {
            "action": "ws_ask",
            "question": "What is the total student dropout count by district?",
            "username": "tester",
            "session_id": "sess_demo_1"
        }
        await ws.send(json.dumps(query_msg))

        # Stream all status events until final result
        while True:
            response_text = await ws.recv()
            data = json.loads(response_text)
            
            if data.get("type") == "status":
                print(f"🔄 [STEP: {data.get('step')}] {data.get('message')}")
            elif data.get("type") == "result":
                print("✅ [FINAL RESULT]:", json.dumps(data.get("data"), indent=2))
                break

if __name__ == "__main__":
    asyncio.run(chat_session_demo())
```

---

## 7. Summary Table of Actions

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
| `ws_cancel` / `cancel` | Cancel in-flight or queued query | `target_request_id`, `request_id` | `result` |
| `ws_ping` / `ping` | Connection heartbeat | `request_id` | `pong` |
