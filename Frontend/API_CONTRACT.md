# API & WebSocket Contract

This project exposes both a high-performance **Real-Time WebSocket Protocol** and a unified multiplexed **HTTP REST Endpoint** for the frontend chatbot interface.

---

## 1. Transport Modes (`VITE_CHATBOT_TRANSPORT`)

The frontend React application supports three transport modes configurable in `.env`:
- `auto` (**Default & Recommended**): Connects via WebSocket for real-time status and query streaming; automatically and seamlessly falls back to HTTP POST if WebSocket connection is unavailable or interrupted.
- `websocket`: Exclusively uses WebSocket connection (`ws://` / `wss://`).
- `http`: Exclusively uses HTTP POST multiplexed endpoint.

---

## 2. WebSocket Protocol (`/ws` & `/ws/chat`)

### Connection Endpoints
- Local development: `ws://localhost:8000/ws` (or `ws://localhost:8000/ws/chat`)
- Production (SSL): `wss://your-domain.com/ws`

### Client Action Payloads

Every client frame is a JSON object with an `action` property:

#### 1. `ws_ask` / `ask` (Chat Query & Planner Progress Stream)
```json
{
  "action": "ws_ask",
  "question": "Show top 5 districts by total student dropouts",
  "username": "user",
  "session_id": "session_abc",
  "request_id": "req_12345"
}
```

**Real-Time Status Frames (`type: "status"`)**:
The server streams progress events as the query passes through the pipeline:
- `step: "queued"` (with `queue_position`)
- `step: "worker_assigned"` (with `worker_id`)
- `step: "guardrail_check"`
- `step: "generating_sql"`
- `step: "formatting"`

**Final Result Frame (`type: "result"`)**:
```json
{
  "type": "result",
  "action": "ws_ask",
  "request_id": "req_12345",
  "session_id": "session_abc",
  "status": "completed",
  "data": {
    "sql": "SELECT district, SUM(dropout_count) as dropouts FROM student_dropouts GROUP BY district ORDER BY dropouts DESC LIMIT 5;",
    "result": [
      {"district": "Visakhapatnam", "dropouts": 1420},
      {"district": "Guntur", "dropouts": 1180}
    ],
    "summary": "Here are the top 5 districts with the highest student dropout counts.",
    "username": "user",
    "timings": {
      "total_time": 1.25
    }
  }
}
```

#### 2. `ws_cancel` / `cancel` (Cancel In-Flight Query)
```json
{
  "action": "ws_cancel",
  "target_request_id": "req_12345",
  "request_id": "req_cancel_cmd"
}
```

#### 3. `ws_history` / `history` (List Session Summaries)
```json
{
  "action": "ws_history",
  "username": "user",
  "request_id": "req_hist_01"
}
```

#### 4. `ws_history_session` / `history_session` (Fetch Full Session History)
```json
{
  "action": "ws_history_session",
  "session_id": "session_abc",
  "username": "user",
  "request_id": "req_sess_01"
}
```

#### 5. `ws_delete_session` / `delete_session` (Delete Session)
```json
{
  "action": "ws_delete_session",
  "session_id": "session_abc",
  "username": "user",
  "request_id": "req_del_01"
}
```

#### 6. `ws_clear_history` / `clear_history` (Clear All Sessions)
```json
{
  "action": "ws_clear_history",
  "username": "user",
  "request_id": "req_clr_01"
}
```

#### 7. `ws_suggestions` & `ws_suggestions_meta` (Suggestions)
```json
{
  "action": "ws_suggestions",
  "limit": 50,
  "request_id": "req_sugg_01"
}
```

#### 8. `ws_chart` / `chart` (Server-Side SVG Chart Rendering)
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

#### 9. `ws_ping` / `ping` (Heartbeat)
```json
{
  "action": "ws_ping",
  "request_id": "ping_01"
}
```

---

## 3. HTTP Multiplexed Endpoint (`POST /ask`)

For clients where WebSockets are unavailable or in HTTP-only fallback mode, all interactions are supported via `POST /ask`.

### Headers
```http
Authorization: Bearer <auth_token>
Content-Type: application/json
```

### Action Dispatch Summary
| Action | Purpose | Required Fields |
|---|---|---|
| `ask` | Execute NL2SQL Query | `question`, `session_id`, `username` |
| `cancel` | Cancel in-flight request | `request_id` or `target_request_id` |
| `history` | List session summaries | `username` |
| `history_session` | Fetch message turns for session | `session_id`, `username` |
| `delete_session` | Delete a single session | `session_id`, `username` |
| `clear_history` | Delete all user sessions | `username` |
| `suggestions_meta` | Suggestions cache metadata | - |
| `suggestions` | Exemplar questions & vectors | `limit` |
| `chart` | SVG chart generation | `chart_type`, `data` |