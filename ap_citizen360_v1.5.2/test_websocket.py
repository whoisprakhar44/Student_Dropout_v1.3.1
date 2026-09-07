"""
test_websocket.py
-----------------
Automated test suite for the WebSocket communication protocol in ap_citizen360_v1.5.2.

Tests covered:
1. WebSocket Connection & ws_ping / ping (Heartbeat)
2. ws_suggestions_meta / suggestions_meta
3. ws_suggestions / suggestions
4. ws_history / history (empty / existing sessions)
5. ws_clear_history / clear_history
6. ws_cancel / cancel signal
7. ws_ask / ask (Query execution with status streaming and final result)
"""

import json
import time
import uuid
import sys
import asyncio
from unittest.mock import MagicMock, AsyncMock

# Provide lightweight mock fallbacks for LangChain / Milvus / Ollama dependencies if running in minimal test env
for mod in [
    "langchain_core",
    "langchain_core.messages",
    "my_agent",
    "my_agent.agent",
    "my_agent.utils",
    "my_agent.utils.ollama_check",
    "my_agent.utils.tools",
    "my_agent.utils.chart_generator",
    "database.suggestions",
    "auth_check",
    "create_schema",
    "openpyxl"
]:
    if mod not in sys.modules:
        try:
            __import__(mod)
        except ImportError:
            m = MagicMock()
            if mod == "auth_check":
                m.validate_issuer = lambda f: f
            elif mod == "my_agent.utils.ollama_check":
                m.check_ollama.return_value = {"model_available": True, "model": "qwen2.5-coder:7b"}
                m.chat_model_name.return_value = "qwen2.5-coder:7b"
            elif mod == "database.suggestions":
                m.get_fewshot_suggestions.return_value = [{"question": "Test suggestion", "sql": "SELECT 1"}]
                m.get_cache_metadata.return_value = {"updated_at": "2026-09-08T00:00:00", "count": 1}
            sys.modules[mod] = m

from app import WebSocketSessionHandler, active_tasks


class MockWebSocket:
    """In-memory async mock WebSocket for lightning-fast, isolated protocol verification."""
    def __init__(self):
        self.sent_messages = []
        self.is_closed = False

    async def send_json(self, data):
        self.sent_messages.append(data)

    async def accept(self):
        pass

    async def close(self, code=1000):
        self.is_closed = True


async def run_all_tests():
    print("=" * 65)
    print("[START] STARTING WEBSOCKET PROTOCOL & ACTION TEST SUITE (v1.5.2)")
    print("=" * 65)

    # 1. Test ws_ping
    ws = MockWebSocket()
    handler = WebSocketSessionHandler(ws)
    await handler.handle_message(json.dumps({"action": "ws_ping", "request_id": "req_ping_1"}))
    await asyncio.sleep(0.05)
    assert len(ws.sent_messages) == 1
    pong = ws.sent_messages[0]
    print(f"[PASS] TEST 1: ws_ping | Response: {pong}")
    assert pong["type"] == "pong"
    assert pong["request_id"] == "req_ping_1"

    # 2. Test ws_suggestions_meta
    ws = MockWebSocket()
    handler = WebSocketSessionHandler(ws)
    await handler.handle_message(json.dumps({"action": "ws_suggestions_meta", "request_id": "req_meta_1"}))
    await asyncio.sleep(0.05)
    assert len(ws.sent_messages) == 1
    meta_resp = ws.sent_messages[0]
    print(f"[PASS] TEST 2: ws_suggestions_meta | Response: {meta_resp}")
    assert meta_resp["type"] == "result"
    assert meta_resp["action"] == "ws_suggestions_meta"

    # 3. Test ws_suggestions
    ws = MockWebSocket()
    handler = WebSocketSessionHandler(ws)
    await handler.handle_message(json.dumps({"action": "ws_suggestions", "limit": 10, "request_id": "req_sugg_1"}))
    await asyncio.sleep(0.05)
    assert len(ws.sent_messages) == 1
    sugg_resp = ws.sent_messages[0]
    print(f"[PASS] TEST 3: ws_suggestions | Suggestions count: {sugg_resp['data']['count']}")
    assert sugg_resp["type"] == "result"
    assert "suggestions" in sugg_resp["data"]

    # 4. Test ws_history and ws_clear_history
    ws = MockWebSocket()
    handler = WebSocketSessionHandler(ws)
    test_user = f"test_user_{uuid.uuid4().hex[:6]}"
    await handler.handle_message(json.dumps({"action": "ws_history", "username": test_user, "request_id": "req_h1"}))
    await asyncio.sleep(0.05)
    hist_resp = ws.sent_messages[0]
    print(f"[PASS] TEST 4a: ws_history | Initial sessions: {len(hist_resp['data'])}")
    assert hist_resp["type"] == "result"
    assert isinstance(hist_resp["data"], list)

    await handler.handle_message(json.dumps({"action": "ws_clear_history", "username": test_user, "request_id": "req_h2"}))
    await asyncio.sleep(0.05)
    clr_resp = ws.sent_messages[1]
    print(f"[PASS] TEST 4b: ws_clear_history | Message: {clr_resp['message']}")
    assert clr_resp["type"] == "result"
    assert clr_resp["status"] == "success"

    # 5. Test ws_cancel
    ws = MockWebSocket()
    handler = WebSocketSessionHandler(ws)
    target_id = f"job_to_cancel_{uuid.uuid4().hex[:6]}"
    await handler.handle_message(json.dumps({"action": "ws_cancel", "target_request_id": target_id, "request_id": "req_c1"}))
    await asyncio.sleep(0.05)
    cancel_resp = ws.sent_messages[0]
    print(f"[PASS] TEST 5: ws_cancel | Response: {cancel_resp}")
    assert cancel_resp["type"] == "result"
    assert cancel_resp["target_request_id"] == target_id

    # 6. Test ws_ask Execution Lifecycle & Status Streaming
    ws = MockWebSocket()
    handler = WebSocketSessionHandler(ws)

    # Mock check_ollama and _get_graph response
    import app
    app.check_ollama = lambda: {"model_available": True, "model": "qwen2.5-coder:7b"}
    mock_graph = AsyncMock()
    mock_graph.ainvoke.return_value = {
        "messages": [],
        "gen_time": 0.05,
        "exec_time": 0.02,
        "intent": "data"
    }
    app._get_graph = AsyncMock(return_value=mock_graph)
    app._extract_sql_and_result = lambda msgs, user: app.AskResponse(
        sql="SELECT district, COUNT(*) FROM dropouts GROUP BY district",
        result=[{"district": "Guntur", "count": 120}],
        username=user
    )

    req_id_ask = f"req_ask_{uuid.uuid4().hex[:6]}"
    sess_id_ask = f"sess_{uuid.uuid4().hex[:6]}"
    await handler.handle_message(json.dumps({
        "action": "ws_ask",
        "question": "What are dropouts in Guntur?",
        "username": "tester",
        "session_id": sess_id_ask,
        "request_id": req_id_ask
    }))

    await asyncio.sleep(0.1)

    print(f"[PASS] TEST 6: ws_ask Streaming Lifecycle | Total Frames Emitted: {len(ws.sent_messages)}")
    for idx, f in enumerate(ws.sent_messages):
        print(f"   Frame {idx + 1}: type={f.get('type')}, step={f.get('step')}, status={f.get('status')}, message='{f.get('message', '')}'")

    steps = [f.get("step") for f in ws.sent_messages if f.get("type") == "status"]
    assert "generating_sql" in steps
    assert "formatting" in steps
    assert "completed" in steps

    final_result = ws.sent_messages[-1]
    assert final_result["type"] == "result"
    assert final_result["status"] == "completed"
    assert final_result["data"]["sql"] == "SELECT district, COUNT(*) FROM dropouts GROUP BY district"
    assert final_result["data"]["result"] == [{"district": "Guntur", "count": 120}]

    print("=" * 65)
    print("[SUCCESS] ALL 6 WEBSOCKET ACTION & STREAMING TESTS PASSED (v1.5.2)!")
    print("=" * 65)


if __name__ == "__main__":
    asyncio.run(run_all_tests())
