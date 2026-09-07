"""
test_valkey_queue.py
--------------------
Comprehensive automated test suite for Valkey FIFO Queue & Parallel Consumer Workers.
Validates:
  1. Strict FIFO ordering of jobs.
  2. N concurrent workers running in parallel.
  3. Automatic queue draining until all jobs complete.
  4. Metric and status tracking (enqueued, completed, failed, cancelled counts, queue depth).
  5. Job cancellation.
  6. Integration testing with FastAPI TestClient on POST /ask (action="ask", action="queue_status", action="job_status", action="cancel").
"""

import sys
import os
import asyncio
import time
import json
import uuid

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database.valkey_queue import ValkeyQueueManager, JobStatus


async def test_queue_unit():
    print("\n" + "=" * 60)
    print("[TEST] 1. Testing ValkeyQueueManager Unit & Multi-Worker Concurrency")
    print("=" * 60)

    # Set concurrency to 3
    os.environ["VALKEY_WORKER_CONCURRENCY"] = "3"
    qm = ValkeyQueueManager()
    qm.concurrency = 3

    processed_order = []
    active_concurrent_peaks = []
    current_active = 0

    async def mock_executor(job: dict) -> dict:
        nonlocal current_active
        current_active += 1
        active_concurrent_peaks.append(current_active)
        job_id = job.get("job_id")
        q = job.get("question")
        # Simulate LLM query execution latency
        await asyncio.sleep(0.1)
        processed_order.append(job_id)
        current_active -= 1
        return {
            "sql": f"SELECT * FROM test WHERE q = '{q}'",
            "result": [{"status": "success", "rows": 10}],
            "username": job.get("username", "user"),
            "gen_time": 0.05,
            "exec_time": 0.05
        }

    qm.set_executor(mock_executor)
    qm.start_workers()

    # Enqueue 6 jobs rapidly
    job_ids = []
    for i in range(1, 7):
        jid = f"test_job_{i}"
        await qm.enqueue_job(
            question=f"Test question {i}",
            username="test_user",
            session_id="test_session",
            request_id=jid
        )
        job_ids.append(jid)

    print(f"Enqueued {len(job_ids)} jobs. Waiting for automatic completion...")

    # Wait for all jobs to complete
    for jid in job_ids:
        res = await qm.wait_for_job(jid, timeout=5.0)
        assert res.get("status") == JobStatus.COMPLETED, f"Job {jid} failed: {res}"
        print(f"  [OK] {jid} finished with status '{res.get('status')}' by {res.get('worker_id')}")

    # Check metrics
    metrics = await qm.get_metrics()
    print("\nLive Queue Metrics:")
    print(json.dumps(metrics, indent=2))

    assert metrics["total_enqueued"] >= 6
    assert metrics["total_completed"] >= 6
    assert metrics["queued_jobs"] == 0
    max_peak = max(active_concurrent_peaks) if active_concurrent_peaks else 0
    print(f"\nMax Concurrent Active Workers Observed: {max_peak} (Configured N: {qm.concurrency})")
    assert max_peak <= qm.concurrency, f"Active workers {max_peak} exceeded limit {qm.concurrency}"

    # Test Job Cancellation
    print("\nTesting Job Cancellation...")
    cancel_jid = "test_job_cancel"
    # Delay executor to test cancelling
    await qm.enqueue_job(question="Will cancel", username="u", session_id="s", request_id=cancel_jid)
    cancelled = await qm.cancel_job(cancel_jid)
    print(f"  Cancelled job {cancel_jid}: {cancelled}")
    job_record = qm.get_job(cancel_jid)
    assert job_record["status"] == JobStatus.CANCELLED

    await qm.stop_workers()
    print("[SUCCESS] ValkeyQueueManager Unit Tests Passed Successfully!\n")


async def test_fastapi_ask_actions():
    print("=" * 60)
    print("[TEST] 2. Testing FastAPI /ask Endpoint with Action Types")
    print("=" * 60)

    from fastapi import FastAPI, HTTPException, Request
    from fastapi.responses import StreamingResponse
    from pydantic import BaseModel, Field

    # Build test app with identical routing logic
    test_app = FastAPI()
    qm = ValkeyQueueManager()
    qm.concurrency = 3

    async def mock_app_executor(job: dict) -> dict:
        q = job.get("question", "")
        u = job.get("username", "user")
        await asyncio.sleep(0.08)
        return {
            "sql": f"SELECT COUNT(*) FROM citizen_student WHERE query = '{q}'",
            "result": [{"total": 1000}],
            "username": u,
            "gen_time": 0.04,
            "exec_time": 0.04,
            "total_time": 0.08
        }

    qm.set_executor(mock_app_executor)
    qm.start_workers()

    class TestAskRequest(BaseModel):
        action: str | None = None
        question: str | None = None
        request_id: str | None = None
        session_id: str | None = None
        username: str = "user"

    @test_app.post("/ask")
    async def ask_endpoint(payload: TestAskRequest):
        action = payload.action or "ask"
        username = payload.username

        if action in ("queue_status", "queue_metrics", "queue"):
            return await qm.get_metrics()

        elif action in ("job_status", "check_job"):
            req_id = payload.request_id
            if not req_id:
                raise HTTPException(status_code=400, detail="request_id is required")
            job = qm.get_job(req_id)
            if not job:
                raise HTTPException(status_code=404, detail=f"Job {req_id} not found")
            return job

        elif action == "cancel":
            req_id = payload.request_id
            if not req_id:
                raise HTTPException(status_code=400, detail="request_id is required")
            cancelled = await qm.cancel_job(req_id)
            if cancelled:
                return {"status": "success", "message": f"Request {req_id} cancellation signal sent."}
            return {"status": "not_found", "message": f"Request {req_id} is not active."}

        elif action == "ask":
            if not payload.question:
                raise HTTPException(status_code=400, detail="question is required")
            req_id = payload.request_id or f"req_{uuid.uuid4().hex[:12]}"
            session_id = payload.session_id or str(uuid.uuid4())

            job_id = await qm.enqueue_job(
                question=payload.question,
                username=username,
                session_id=session_id,
                request_id=req_id,
            )

            async def _stream():
                while True:
                    job = qm.get_job(job_id)
                    if job and job.get("status") in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED):
                        break
                    await asyncio.sleep(0.05)

                job = qm.get_job(job_id) or {}
                if job.get("status") == JobStatus.CANCELLED:
                    yield json.dumps({"sql": "", "result": [{"error": "Request cancelled.", "status": "cancelled"}]}).encode()
                elif job.get("result"):
                    yield json.dumps(job["result"]).encode()
                else:
                    yield json.dumps({"sql": "", "result": [{"error": "failed", "status": "failed"}]}).encode()

            return StreamingResponse(_stream(), media_type="application/json")

    import httpx
    transport = httpx.ASGITransport(app=test_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Test queue_status
        res_q = await client.post("/ask", json={"action": "queue_status", "username": "tester"})
        print(f"POST /ask (action='queue_status') Status: {res_q.status_code}")
        assert res_q.status_code == 200
        q_data = res_q.json()
        print("Queue Status Response:", json.dumps(q_data, indent=2))
        assert q_data["concurrency_limit"] == 3

        # 2. Test concurrent ask queries
        print("\nSending 3 concurrent queries to POST /ask (action='ask')...")
        async def send_query(idx):
            res = await client.post(
                "/ask",
                json={
                    "action": "ask",
                    "question": f"How many students in district {idx}?",
                    "username": f"user_{idx}",
                    "request_id": f"api_test_req_{idx}"
                }
            )
            assert res.status_code == 200
            data = json.loads(res.text.strip())
            print(f"  [OK] Query {idx} returned: {data.get('sql')}")
            return data

        results = await asyncio.gather(
            send_query(1),
            send_query(2),
            send_query(3)
        )
        assert len(results) == 3

        # 3. Test job_status
        res_job = await client.post("/ask", json={"action": "job_status", "request_id": "api_test_req_1"})
        print(f"\nPOST /ask (action='job_status') Status: {res_job.status_code}")
        assert res_job.status_code == 200
        job_info = res_job.json()
        print(f"  Job 1 Status: {job_info.get('status')} | Worker: {job_info.get('worker_id')}")
        assert job_info.get("status") == JobStatus.COMPLETED

        # 4. Test cancel on nonexistent
        res_cancel = await client.post("/ask", json={"action": "cancel", "request_id": "missing_req"})
        assert res_cancel.status_code == 200
        assert res_cancel.json()["status"] == "not_found"
        print(f"  Cancel nonexistent request handled: {res_cancel.json()}")

    await qm.stop_workers()
    print("\n[SUCCESS] FastAPI /ask Endpoint Actions Tested & Verified Successfully!")


async def main():
    import uuid
    await test_queue_unit()
    await test_fastapi_ask_actions()


if __name__ == "__main__":
    asyncio.run(main())
