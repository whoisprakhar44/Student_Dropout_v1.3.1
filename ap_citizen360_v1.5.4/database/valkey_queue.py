"""
valkey_queue.py
---------------
Valkey-backed FIFO query queue and parallel consumer worker pool.

Features:
  - Strict FIFO query scheduling (1-by-1 in arrival order).
  - Configurable N concurrent worker consumers processing LLM queries in parallel.
  - Concurrency controlled via VALKEY_WORKER_CONCURRENCY / MAX_CONCURRENT_WORKERS env var.
  - Detailed structured logging: entry, worker assignment, status transitions,
    execution progress, timings, completion stats, and remaining queue depth.
  - Comprehensive queue metrics: total enqueued, completed, failed, cancelled, active count, queue depth.
  - Resilient design: connects to Valkey server if available, with transparent
    in-memory asynchronous queue fallback for environments without a running Valkey daemon.
  - Asynchronous event notifications for non-blocking HTTP streaming with keepalives.
  - Full support for job cancellation.
"""

import os
import json
import time
import uuid
import logging
import asyncio
from datetime import datetime
from typing import Dict, Any, Optional, Callable, Awaitable
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("valkey_queue")


class JobStatus:
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ValkeyQueueManager:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(ValkeyQueueManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if getattr(self, "_initialized", False):
            return

        # 1. Concurrency limit N (from environment)
        concurrency_str = os.environ.get(
            "VALKEY_WORKER_CONCURRENCY",
            os.environ.get("MAX_CONCURRENT_WORKERS", "3")
        )
        try:
            self.concurrency = max(1, int(concurrency_str))
        except ValueError:
            self.concurrency = 3

        # 2. Valkey connection config
        self.valkey_url = os.environ.get("VALKEY_URL", "redis://localhost:6379/0")
        self.queue_key = "valkey:query_queue"
        self.jobs_prefix = "valkey:job:"
        self.metrics_key = "valkey:queue_metrics"
        self.active_set_key = "valkey:active_jobs"

        # 3. Connection state
        self.valkey_client = None
        self.is_connected = False
        self._init_valkey_client()

        # 4. In-memory fallback and event synchronization
        self._fallback_queue: asyncio.Queue[str] = asyncio.Queue()
        self._job_store: Dict[str, Dict[str, Any]] = {}
        self._job_events: Dict[str, asyncio.Event] = {}
        self._active_worker_tasks: Dict[str, asyncio.Task] = {}  # job_id -> worker task
        self._worker_pool_tasks: list[asyncio.Task] = []
        self._is_running = False
        self._executor_callback: Optional[Callable[[Dict[str, Any]], Awaitable[Dict[str, Any]]]] = None

        # 5. Local counters (synced with Valkey if available)
        self.total_enqueued = 0
        self.total_completed = 0
        self.total_failed = 0
        self.total_cancelled = 0

        self._initialized = True
        logger.info(
            "[QUEUE INIT] ValkeyQueueManager initialized | Concurrency (N): %d | Mode: %s",
            self.concurrency,
            "Valkey Server" if self.is_connected else "In-Memory Fallback Queue"
        )

    def _init_valkey_client(self):
        """Try connecting to Valkey / Redis instance."""
        try:
            from valkey import Valkey
            client = Valkey.from_url(
                self.valkey_url,
                decode_responses=True,
                socket_connect_timeout=1.5,
                socket_timeout=1.5
            )
            # Test ping
            client.ping()
            self.valkey_client = client
            self.is_connected = True
            logger.info("Connected to Valkey server at %s", self.valkey_url)
        except Exception as e:
            self.valkey_client = None
            self.is_connected = False
            logger.warning(
                "Valkey server at %s not reachable (%s). Using in-memory async FIFO queue fallback.",
                self.valkey_url,
                e
            )

    def set_executor(self, callback: Callable[[Dict[str, Any]], Awaitable[Dict[str, Any]]]):
        """Register the async function that runs the query execution graph."""
        self._executor_callback = callback

    # ──────────────────────────────────────────────────────────────────────────
    # Queue Operations
    # ──────────────────────────────────────────────────────────────────────────

    async def enqueue_job(
        self,
        question: str,
        username: str,
        session_id: str,
        request_id: Optional[str] = None,
        payload_meta: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Enqueue an incoming user query in strict FIFO order.
        Returns the unique request_id / job_id.
        """
        job_id = request_id or f"req_{uuid.uuid4().hex[:12]}"
        now_iso = datetime.now().isoformat()

        job_data: Dict[str, Any] = {
            "job_id": job_id,
            "question": question,
            "username": username,
            "session_id": session_id,
            "status": JobStatus.QUEUED,
            "enqueued_at": now_iso,
            "started_at": None,
            "completed_at": None,
            "worker_id": None,
            "gen_time": 0.0,
            "exec_time": 0.0,
            "total_time": 0.0,
            "wait_time": 0.0,
            "result": None,
            "error": None,
            "meta": payload_meta or {}
        }

        # Store job record
        self._job_store[job_id] = job_data
        self._job_events[job_id] = asyncio.Event()

        # Update metrics
        self.total_enqueued += 1

        if self.is_connected and self.valkey_client:
            try:
                # Save job hash/JSON in Valkey
                self.valkey_client.set(f"{self.jobs_prefix}{job_id}", json.dumps(job_data))
                # Push job_id to the right side of the list (FIFO entry)
                self.valkey_client.rpush(self.queue_key, job_id)
                self.valkey_client.hincrby(self.metrics_key, "total_enqueued", 1)
            except Exception as e:
                logger.error("Valkey enqueue failed, falling back to in-memory: %s", e)
                await self._fallback_queue.put(job_id)
        else:
            await self._fallback_queue.put(job_id)

        queue_len = await self.get_queue_length()
        logger.info(
            "[QUEUE ENQUEUE] Job ID: %s | User: '%s' | Queue Length: %d | Question: '%s'",
            job_id,
            username,
            queue_len,
            (question[:60] + "...") if len(question) > 60 else question
        )

        return job_id

    async def get_queue_length(self) -> int:
        """Get current number of waiting queries in queue."""
        if self.is_connected and self.valkey_client:
            try:
                return self.valkey_client.llen(self.queue_key)
            except Exception:
                pass
        return self._fallback_queue.qsize()

    async def _dequeue_next_job(self) -> Optional[str]:
        """Pop the next job_id from the FIFO queue (left pop)."""
        if self.is_connected and self.valkey_client:
            try:
                # Non-blocking LPOP
                job_id = self.valkey_client.lpop(self.queue_key)
                if job_id:
                    return job_id
            except Exception as e:
                logger.error("Valkey dequeue error: %s", e)

        # Fallback in-memory queue
        if not self._fallback_queue.empty():
            try:
                return self._fallback_queue.get_nowait()
            except asyncio.QueueEmpty:
                return None
        return None

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve the job dictionary by ID."""
        if self.is_connected and self.valkey_client:
            try:
                val = self.valkey_client.get(f"{self.jobs_prefix}{job_id}")
                if val:
                    data = json.loads(val)
                    # Sync local store with Valkey
                    self._job_store[job_id] = data
                    return data
            except Exception:
                pass
        return self._job_store.get(job_id)

    def _update_job(self, job_id: str, updates: Dict[str, Any]):
        """Update job fields in both local cache and Valkey."""
        job = self._job_store.get(job_id, {})
        job.update(updates)
        self._job_store[job_id] = job

        if self.is_connected and self.valkey_client:
            try:
                self.valkey_client.set(f"{self.jobs_prefix}{job_id}", json.dumps(job))
            except Exception as e:
                logger.error("Failed to update job in Valkey: %s", e)

    async def wait_for_job(self, job_id: str, timeout: Optional[float] = None) -> Dict[str, Any]:
        """Await the completion event for a specific job."""
        event = self._job_events.get(job_id)
        if not event:
            event = asyncio.Event()
            self._job_events[job_id] = event

        job = self.get_job(job_id)
        if job and job.get("status") in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED):
            return job

        if timeout:
            await asyncio.wait_for(event.wait(), timeout=timeout)
        else:
            await event.wait()

        return self.get_job(job_id) or {}

    async def cancel_job(self, job_id: str) -> bool:
        """Cancel a queued or actively processing job."""
        job = self.get_job(job_id)
        if not job:
            return False

        current_status = job.get("status")
        if current_status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED):
            return False

        logger.info("[QUEUE CANCEL] Cancelling Job ID: %s (Status was: %s)", job_id, current_status)
        self._update_job(job_id, {
            "status": JobStatus.CANCELLED,
            "completed_at": datetime.now().isoformat(),
            "error": "Request cancelled by user."
        })
        self.total_cancelled += 1

        # Cancel running task if active
        active_task = self._active_worker_tasks.get(job_id)
        if active_task and not active_task.done():
            active_task.cancel()

        # Signal completion event
        event = self._job_events.get(job_id)
        if event:
            event.set()

        return True

    # --------------------------------------------------------------------------
    # Consumer Worker Pool Lifecycle
    # --------------------------------------------------------------------------

    def start_workers(self, loop: Optional[asyncio.AbstractEventLoop] = None):
        """Start N parallel consumer worker tasks."""
        if self._is_running:
            logger.warning("Worker pool is already running.")
            return

        self._is_running = True
        self._worker_pool_tasks.clear()

        logger.info("=" * 70)
        logger.info("[STARTING WORKER POOL] Spawning %d concurrent worker consumers...", self.concurrency)
        logger.info("=" * 70)

        for i in range(1, self.concurrency + 1):
            worker_id = f"worker-{i}"
            task = asyncio.create_task(self._worker_loop(worker_id), name=worker_id)
            self._worker_pool_tasks.append(task)

    async def stop_workers(self):
        """Gracefully stop worker pool."""
        logger.info("[STOPPING WORKERS] Stopping %d worker consumers...", len(self._worker_pool_tasks))
        self._is_running = False
        for task in self._worker_pool_tasks:
            task.cancel()
        await asyncio.gather(*self._worker_pool_tasks, return_exceptions=True)
        self._worker_pool_tasks.clear()
        logger.info("All worker consumers stopped.")

    async def _worker_loop(self, worker_id: str):
        """
        Continuous consumer loop for worker_id.
        Drains queries from the queue 1 by 1 in FIFO order.
        Executes concurrently with other workers up to N concurrency.
        """
        logger.info("[WORKER READY] %s listening for incoming queries...", worker_id)
        while self._is_running:
            try:
                job_id = await self._dequeue_next_job()
                if not job_id:
                    # Queue is empty, pause briefly before next check
                    await asyncio.sleep(0.15)
                    continue

                job = self.get_job(job_id)
                if not job or job.get("status") == JobStatus.CANCELLED:
                    continue

                # Process the job
                await self._process_job(worker_id, job_id, job)

            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("Unhandled error in %s loop: %s", worker_id, exc, exc_info=True)
                await asyncio.sleep(0.5)

    async def _process_job(self, worker_id: str, job_id: str, job: Dict[str, Any]):
        """Execute a single query job through the registered executor."""
        enqueued_at = job.get("enqueued_at")
        t_enqueue = datetime.fromisoformat(enqueued_at).timestamp() if enqueued_at else time.time()
        wait_time = time.time() - t_enqueue
        started_at_iso = datetime.now().isoformat()

        # Update status to PROCESSING
        self._update_job(job_id, {
            "status": JobStatus.PROCESSING,
            "started_at": started_at_iso,
            "worker_id": worker_id,
            "wait_time": round(wait_time, 2)
        })

        if self.is_connected and self.valkey_client:
            try:
                self.valkey_client.sadd(self.active_set_key, job_id)
            except Exception:
                pass

        active_count = len(self._active_worker_tasks) + 1
        rem_queue = await self.get_queue_length()

        logger.info("-" * 70)
        logger.info(
            "[%s START] Job ID: %s | User: '%s' | Wait in Queue: %.2fs | Active Workers: %d/%d | Remaining: %d",
            worker_id,
            job_id,
            job.get("username"),
            wait_time,
            active_count,
            self.concurrency,
            rem_queue
        )
        logger.info("   Question: %s", job.get("question"))
        logger.info("-" * 70)

        t_start = time.perf_counter()
        current_task = asyncio.current_task()
        self._active_worker_tasks[job_id] = current_task

        try:
            if not self._executor_callback:
                raise RuntimeError("No query executor callback registered in ValkeyQueueManager.")

            # Execute the LangGraph query via the callback
            exec_result = await self._executor_callback(job)

            total_time = time.perf_counter() - t_start
            gen_time = exec_result.get("gen_time", 0.0)
            exec_time = exec_result.get("exec_time", 0.0)

            # Determine success vs error in result
            result_rows = exec_result.get("result", [])
            has_error = (
                isinstance(result_rows, list)
                and len(result_rows) > 0
                and result_rows[0].get("status") in ("failed", "cancelled")
            )

            status = JobStatus.FAILED if has_error else JobStatus.COMPLETED
            if status == JobStatus.COMPLETED:
                self.total_completed += 1
            else:
                self.total_failed += 1

            self._update_job(job_id, {
                "status": status,
                "completed_at": datetime.now().isoformat(),
                "gen_time": round(gen_time, 2),
                "exec_time": round(exec_time, 2),
                "total_time": round(total_time, 2),
                "result": exec_result,
                "error": result_rows[0].get("error") if has_error else None
            })

            logger.info("=" * 70)
            logger.info(
                "[%s DONE] Job ID: %s | Status: %s | Total Time: %.2fs (Gen: %.2fs, Exec: %.2fs)",
                worker_id,
                job_id,
                status.upper(),
                total_time,
                gen_time,
                exec_time
            )
            logger.info("   SQL Generated : %s", exec_result.get("sql") or "None")
            logger.info("   Result Rows   : %d", len(result_rows) if isinstance(result_rows, list) else 0)
            logger.info(
                "   Queue Summary : Completed: %d | Failed: %d | Remaining in Queue: %d",
                self.total_completed,
                self.total_failed,
                await self.get_queue_length()
            )
            logger.info("=" * 70)

        except asyncio.CancelledError:
            total_time = time.perf_counter() - t_start
            self.total_cancelled += 1
            self._update_job(job_id, {
                "status": JobStatus.CANCELLED,
                "completed_at": datetime.now().isoformat(),
                "total_time": round(total_time, 2),
                "error": "Execution cancelled."
            })
            logger.warning("[%s CANCELLED] Job ID: %s cancelled after %.2fs", worker_id, job_id, total_time)

        except Exception as exc:
            total_time = time.perf_counter() - t_start
            self.total_failed += 1
            self._update_job(job_id, {
                "status": JobStatus.FAILED,
                "completed_at": datetime.now().isoformat(),
                "total_time": round(total_time, 2),
                "error": str(exc),
                "result": {
                    "sql": "",
                    "result": [{"error": str(exc), "status": "failed"}],
                    "username": job.get("username", "user")
                }
            })
            logger.error("[%s ERROR] Job ID: %s failed after %.2fs: %s", worker_id, job_id, total_time, exc, exc_info=True)

        finally:
            self._active_worker_tasks.pop(job_id, None)
            if self.is_connected and self.valkey_client:
                try:
                    self.valkey_client.srem(self.active_set_key, job_id)
                except Exception:
                    pass

            # Notify any waiting HTTP response streams
            event = self._job_events.get(job_id)
            if event:
                event.set()

    # ──────────────────────────────────────────────────────────────────────────
    # Metrics & Observability
    # ──────────────────────────────────────────────────────────────────────────

    async def get_metrics(self) -> Dict[str, Any]:
        """Return comprehensive live status and metrics of the queue."""
        queue_len = await self.get_queue_length()
        active_count = len(self._active_worker_tasks)

        # Recent 10 jobs summary
        recent_jobs = []
        for jid in reversed(list(self._job_store.keys())[-10:]):
            j = self._job_store.get(jid, {})
            recent_jobs.append({
                "job_id": jid,
                "username": j.get("username"),
                "question": j.get("question"),
                "status": j.get("status"),
                "enqueued_at": j.get("enqueued_at"),
                "total_time": j.get("total_time"),
                "worker_id": j.get("worker_id"),
            })

        return {
            "status": "healthy" if self._is_running else "stopped",
            "backend": "valkey" if self.is_connected else "in_memory_fallback",
            "concurrency_limit": self.concurrency,
            "active_workers": active_count,
            "queued_jobs": queue_len,
            "total_enqueued": self.total_enqueued,
            "total_completed": self.total_completed,
            "total_failed": self.total_failed,
            "total_cancelled": self.total_cancelled,
            "recent_jobs": recent_jobs,
            "timestamp": datetime.now().isoformat(),
        }
