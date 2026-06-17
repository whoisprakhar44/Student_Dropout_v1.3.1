import asyncio
import httpx
import sys
import subprocess
import os
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path("/Users/prakhar/Downloads/Student_Dropout_v1.3.1")
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import init_history_database

async def run_tests_async():
    print("Initializing test database...")
    init_history_database()
    
    port = 8005
    url = f"http://127.0.0.1:{port}"
    
    print(f"Starting background uvicorn server on port {port}...")
    env = os.environ.copy()
    env["PYTHONPATH"] = str(PROJECT_ROOT) + (":" + env.get("PYTHONPATH", "") if env.get("PYTHONPATH") else "")
    
    # Open log files
    stdout_log = open(os.path.join(PROJECT_ROOT, "uvicorn_stdout.log"), "w")
    stderr_log = open(os.path.join(PROJECT_ROOT, "uvicorn_stderr.log"), "w")
    
    server_process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app:app", "--host", "127.0.0.1", "--port", str(port)],
        cwd=str(PROJECT_ROOT),
        env=env,
        stdout=stdout_log,
        stderr=stderr_log
    )
    
    # Wait for server to start
    print("Waiting for server to become healthy...")
    server_ready = False
    async with httpx.AsyncClient() as client:
        for _ in range(30):
            try:
                r = await client.get(f"{url}/health")
                if r.status_code == 200:
                    server_ready = True
                    break
            except Exception:
                pass
            await asyncio.sleep(0.5)
            
    if not server_ready:
        server_process.terminate()
        server_process.wait()
        print("Uvicorn failed to start.")
        sys.exit(1)
        
    print("Server is ready. Running tests...")
    
    try:
        async with httpx.AsyncClient(base_url=url, timeout=30.0) as client:
            # 1. Clear history scoped by username
            username_test = "test_user_dropout"
            print(f"Clearing history for username: {username_test}")
            r = await client.delete(f"/history?username={username_test}")
            assert r.status_code == 200, f"Expected 200, got {r.status_code}"
            
            # 2. Get history list and verify empty
            r = await client.get(f"/history?username={username_test}")
            assert r.status_code == 200
            sessions = r.json()
            assert len(sessions) == 0, f"Expected 0 sessions, got {len(sessions)}"
            print("Scoped history check on empty database: OK")
            
            # 3. Submit question via /ask
            q = "How many schools are functional?"
            print(f"Submitting Q: '{q}' for username: {username_test}")
            payload = {
                "question": q,
                "username": username_test
            }
            # Since the /ask is streaming, we use stream() context manager
            async with client.stream("POST", "/ask", json=payload) as r:
                assert r.status_code == 200
                content_bytes = bytearray()
                async for chunk in r.aiter_bytes():
                    content_bytes.extend(chunk)
            
            content = content_bytes.decode("utf-8")
            print(f"Raw response content: {content}")
            
            # Parse the final JSON from the stream (it might be prefixed with spaces for keepalive)
            chunks = content.strip().split("\n")
            final_chunk = chunks[-1].strip()
            
            import json
            data = json.loads(final_chunk)
            print(f"Parsed response object: {data}")
            
            assert "session_id" in data
            assert "sql" in data
            assert "result" in data
            assert "response" in data
            
            session_id = data["session_id"]
            print(f"Generated Session ID: {session_id}")
            
            # 4. Check that /history now lists this session
            r = await client.get(f"/history?username={username_test}")
            assert r.status_code == 200
            sessions = r.json()
            assert len(sessions) == 1, f"Expected 1 session, got {len(sessions)}"
            assert sessions[0]["id"] == session_id
            print("History list displays newly created session: OK")
            
            # 5. Check session details
            r = await client.get(f"/history/{session_id}")
            assert r.status_code == 200
            details = r.json()
            assert details["id"] == session_id
            assert len(details["messages"]) == 2 # 1 User turn, 1 Assistant turn
            print("Session detail verification: OK")
            
            # 6. Check deletion
            r = await client.delete(f"/history/{session_id}")
            assert r.status_code == 200
            
            # 7. Check session is gone
            r = await client.get(f"/history?username={username_test}")
            sessions = r.json()
            assert len(sessions) == 0
            print("Session deletion: OK")
            
            print("\n🎉 ALL HISTORY INTEGRATION TESTS PASSED SUCCESSFULLY! 🎉")
            
    finally:
        print("Stopping uvicorn server...")
        server_process.terminate()
        server_process.wait()

def run_tests():
    asyncio.run(run_tests_async())

if __name__ == "__main__":
    run_tests()
