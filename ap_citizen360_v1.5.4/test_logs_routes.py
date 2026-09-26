"""
test_logs_routes.py
Comprehensive integration test suite for TOTP-authenticated live logs endpoints in 1.5.4.
"""

import time
import struct
import hmac
import hashlib
import base64
import json
from starlette.testclient import TestClient

from app import app
from log_streamer import get_totp_secret, verify_totp, log_manager, SESSION_COOKIE_NAME


def generate_current_totp(secret_base32: str) -> str:
    key = base64.b32decode(secret_base32, casefold=True)
    current_step = int(time.time() // 30)
    msg = struct.pack(">Q", current_step)
    h = hmac.new(key, msg, hashlib.sha1).digest()
    offset = h[-1] & 0x0F
    truncated = struct.unpack(">I", h[offset:offset + 4])[0] & 0x7FFFFFFF
    return str(truncated % 1000000).zfill(6)


def run_tests():
    secret = get_totp_secret()
    print(f"=== TESTING TOTP LOGS ROUTES 1.5.4 (Secret: {secret}) ===")
    
    with TestClient(app) as client:
        # 1. Unauthenticated /logs UI (and verify secret is not leaked)
        r = client.get("/logs")
        assert r.status_code == 200
        assert "Runtime Logs Access" in r.text
        assert "6-DIGIT VERIFICATION CODE" in r.text
        assert "LOGS_AUTH_SECRET" not in r.text
        assert f"Current Secret: <code>{secret}</code>" not in r.text
        print("[PASS] 1. GET /logs renders unauthenticated TOTP login form (secret not exposed)")

        # 2. Invalid TOTP submission (GET & POST)
        r = client.get("/logs?code=000000")
        assert r.status_code == 200
        assert "Invalid or expired 6-digit Authenticator code" in r.text
        
        r_post_inv = client.post("/logs", data={"code": "000000"})
        assert r_post_inv.status_code == 200
        assert "Invalid or expired 6-digit Authenticator code" in r_post_inv.text
        print("[PASS] 2. GET/POST /logs with invalid code rejected with error")

        # 3. Valid TOTP submission via POST form -> sets cookie & returns dashboard
        valid_totp = generate_current_totp(secret)
        r = client.post("/logs", data={"code": valid_totp, "action": "logs"})
        assert r.status_code == 200
        assert "Live Runtime Logs" in r.text
        assert SESSION_COOKIE_NAME in client.cookies
        print(f"[PASS] 3. POST /logs form submission with code={valid_totp} authenticates and sets session cookie")

        # 4. GET /logs?action=logs_data using session cookie
        r = client.get("/logs?action=logs_data")
        assert r.status_code == 200
        data = r.json()
        assert data.get("status") == "success"
        assert "logs" in data
        assert isinstance(data["logs"], list)
        print(f"[PASS] 4. GET /logs?action=logs_data returns JSON logs ({len(data['logs'])} buffered entries)")

        # 5. GET /logs?action=logs_data without auth in new client
        fresh_client = TestClient(app)
        r = fresh_client.get("/logs?action=logs_data")
        assert r.status_code == 401
        print("[PASS] 5. GET /logs?action=logs_data without auth rejected with 401")

        # 6. GET /logs?action=logs_data with Bearer token header
        r = fresh_client.get("/logs?action=logs_data", headers={"Authorization": f"Bearer {valid_totp}"})
        assert r.status_code == 200
        assert r.json().get("status") == "success"
        print("[PASS] 6. GET /logs?action=logs_data accepts Bearer TOTP token")

        # 7. GET /logs?action=logs_stream without auth returns unauthorized SSE payload and completes
        r = fresh_client.get("/logs?action=logs_stream")
        assert r.status_code == 200
        assert "text/event-stream" in r.headers["content-type"]
        assert "Unauthorized: TOTP verification required" in r.text
        print("[PASS] 7. GET /logs?action=logs_stream unauthorized SSE stream verified")

        # 8. Logout clears cookie
        r = client.get("/logs?logout=1")
        assert r.status_code == 200
        assert "Runtime Logs Access" in r.text
        assert client.cookies.get(SESSION_COOKIE_NAME) is None or client.cookies.get(SESSION_COOKIE_NAME) == '""'
        print("[PASS] 8. GET /logs?logout=1 clears session cookie")

        # 9. WebSocket /ws logs streaming test
        with client.websocket_connect("/ws") as ws:
            # 9a. Unauthorized ws_logs
            ws.send_json({"action": "ws_logs", "code": "000000", "request_id": "req_log_fail"})
            res = ws.receive_json()
            assert res.get("type") == "error"
            assert "Unauthorized" in res.get("detail", "")
            print("[PASS] 9a. WS ws_logs rejected invalid code")

            # 9b. Authorized ws_logs
            ws.send_json({"action": "ws_logs", "code": valid_totp, "request_id": "req_log_ok"})
            status_res = ws.receive_json()
            assert status_res.get("type") == "status"
            assert status_res.get("status") == "connected"

            # Should receive buffered log frames
            log_res = ws.receive_json()
            assert log_res.get("type") == "log"
            assert "data" in log_res
            assert "formatted" in log_res["data"]
            print(f"[PASS] 9b. WS ws_logs connected and received log frames: {log_res['data']['message'][:40]}...")

    print("\n=======================================================")
    print(">>> ALL TOTP LIVE LOGS INTEGRATION TESTS PASSED (1.5.4)! <<<")
    print("=======================================================\n")


if __name__ == "__main__":
    run_tests()
