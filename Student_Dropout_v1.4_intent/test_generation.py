#!/usr/bin/env python3
"""
Test script to run all few-shot questions directly through the LangGraph agent,
measuring generation time and success status.

Usage:
    python test_generation.py              # Run all fewshots
    python test_generation.py --limit 2   # Quick smoke-test with first 2 entries
"""

import sys
import asyncio
import re
import time
import json
import logging
import argparse
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
ROOT_DIR = Path(__file__).resolve().parent
sys.path.append(str(ROOT_DIR))

# Handle sqlite3 fallback first (same as app.py)
try:
    import pysqlite3
    sys.modules["sqlite3"] = pysqlite3
except ImportError:
    pass

from dataclasses import dataclass, field
from typing import Any

from langchain_core.messages import HumanMessage
from my_agent.agent import build_graph

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
# NOTE: We intentionally do NOT import anything from app.py.
# app.py owns chat history, sessions, and memory continuity — none of which
# belong in an isolated benchmark run.  The helpers below are minimal, self-
# contained copies of the logic we actually need.
FEWSHOTS_PATH = ROOT_DIR / "school_dropout_fewshots_combined.jsonl"
LOGS_DIR = ROOT_DIR / "generation_logs"


# ---------------------------------------------------------------------------
# Minimal response type (no DB, no username scoping, no memory)
# ---------------------------------------------------------------------------
@dataclass
class _QueryResult:
    """Lightweight stand-in for app.AskResponse — carries only sql + rows."""
    sql: str = ""
    result: list[dict[str, Any]] = field(default_factory=list)


def _extract_tool_content(message: Any) -> str | None:
    """Pull plain-text content out of a ToolMessage (string or content-block list)."""
    raw = getattr(message, "content", None)
    if raw is None:
        return None
    if isinstance(raw, str):
        return raw
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, str):
                return item
            if isinstance(item, dict) and item.get("type") == "text":
                return item.get("text")
    return str(raw)


def _extract_sql_and_result(messages: list[Any]) -> _QueryResult:
    """
    Scan the finished LangGraph message list and return the generated SQL
    and the execute_sql result rows.

    Completely self-contained — no DB access, no session lookup, no memory.
    """
    from langchain_core.messages import ToolMessage as LCToolMessage

    sql: str | None = None
    result: list[dict[str, Any]] | None = None

    for message in messages:
        # Extract SQL from any AIMessage that called execute_sql
        for tool_call in getattr(message, "tool_calls", None) or []:
            args = tool_call.get("args") or {}
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    args = {}
            if tool_call.get("name") == "execute_sql" and args.get("query"):
                sql = args["query"]

        # Extract rows from the ToolMessage returned by execute_sql
        is_tool_msg = isinstance(message, LCToolMessage) or (
            message.__class__.__name__ == "ToolMessage"
        )
        if not is_tool_msg:
            continue
        if getattr(message, "name", None) != "execute_sql":
            continue

        raw_content = _extract_tool_content(message)
        if not raw_content:
            continue
        try:
            payload = json.loads(raw_content)
        except (json.JSONDecodeError, TypeError, ValueError):
            continue
        if payload.get("status") == "success":
            result = payload.get("rows") or []

    # Defaults / fallback error payload
    if sql is None:
        sql = ""
    if result is None:
        error_msg = None
        for message in reversed(messages):
            is_tool_msg = isinstance(message, LCToolMessage) or (
                message.__class__.__name__ == "ToolMessage"
            )
            if is_tool_msg and getattr(message, "name", None) == "execute_sql":
                raw_content = _extract_tool_content(message)
                if raw_content:
                    try:
                        p = json.loads(raw_content)
                        if p.get("status") == "error":
                            error_msg = p.get("error_msg") or p.get("error_type")
                            if error_msg:
                                break
                    except Exception:
                        pass
        if not error_msg:
            for message in reversed(messages):
                if not getattr(message, "tool_calls", None):
                    content = getattr(message, "content", None)
                    if content and isinstance(content, str) and content.strip():
                        error_msg = content.strip()
                        break
        if not error_msg:
            error_msg = "The agent did not return an executed SQL query."
        result = [{"error": error_msg, "status": "failed"}]

    return _QueryResult(sql=sql, result=result)


# ---------------------------------------------------------------------------
# Stdout Tee — mirrors every print() call into the log file as well
# ---------------------------------------------------------------------------
class _TeeStream:
    """Wraps sys.stdout so every write goes to both the terminal and the log file."""

    def __init__(self, original_stream, file_handle):
        self._orig = original_stream
        self._file = file_handle

    def write(self, data: str) -> int:
        self._orig.write(data)
        self._file.write(data)
        return len(data)

    def flush(self):
        self._orig.flush()
        self._file.flush()

    def fileno(self):
        return self._orig.fileno()

    # Forward any other attribute lookups to the original stream
    def __getattr__(self, name):
        return getattr(self._orig, name)


# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------
def setup_logging() -> tuple[logging.Logger, Path]:
    """
    Capture EVERYTHING that appears on the terminal into a per-run log file:

    1. Our own gen_test logger  → file (DEBUG) + console (INFO)
    2. Root logger              → file (DEBUG) — catches all module loggers
                                  (MCP, schema-retrieval, LangChain, etc.)
    3. sys.stdout Tee           → file — catches print() calls from agent code
    """
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = LOGS_DIR / f"generation_test_{timestamp}.log"

    # Open the log file once; both the logging handler and the Tee share it.
    log_file = open(log_path, "w", encoding="utf-8")  # noqa: WPS515

    fmt = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # ── 1. gen_test logger (our own structured output) ──────────────────────
    logger = logging.getLogger("gen_test")
    logger.setLevel(logging.DEBUG)
    if logger.handlers:
        logger.handlers.clear()

    fh = logging.StreamHandler(log_file)   # write to the shared file handle
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)

    sh = logging.StreamHandler(sys.stdout)
    sh.setLevel(logging.INFO)
    sh.setFormatter(fmt)

    logger.addHandler(fh)
    logger.addHandler(sh)
    logger.propagate = False  # don't double-log via root

    # ── 2. Root logger → file only (all 3rd-party module loggers) ───────────
    root = logging.getLogger()
    # Remove any existing file handlers pointing at our log to avoid duplicates
    root.handlers = [h for h in root.handlers if not isinstance(h, logging.FileHandler)]
    root_fh = logging.StreamHandler(log_file)
    root_fh.setLevel(logging.DEBUG)
    root_fh.setFormatter(fmt)
    root.addHandler(root_fh)
    if root.level == logging.NOTSET or root.level > logging.DEBUG:
        root.setLevel(logging.DEBUG)

    # ── 3. Tee stdout → file (captures print() from agent/MCP/tools code) ───
    sys.stdout = _TeeStream(sys.__stdout__, log_file)

    return logger, log_path


# ---------------------------------------------------------------------------
# SQL normalisation helper
# ---------------------------------------------------------------------------
def normalize_sql(sql: str) -> str:
    if not sql:
        return ""
    sql = sql.replace("curated_datamodels.", "")
    sql = sql.lower()
    sql = re.sub(r"\s+", " ", sql).strip()
    sql = sql.rstrip(";").strip()
    return sql


# ---------------------------------------------------------------------------
# Main async test runner
# ---------------------------------------------------------------------------
async def test_all_generations(limit: int | None = None) -> None:
    log, log_path = setup_logging()

    session_start = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log.info("=" * 80)
    log.info(f"SESSION START  {session_start}  (limit={limit if limit else 'ALL'})")
    log.info("=" * 80)

    # ---- Load fewshots ----
    if not FEWSHOTS_PATH.is_file():
        log.error(f"Fewshots file not found: {FEWSHOTS_PATH}")
        sys.exit(1)

    log.info(f"Reading few-shots from: {FEWSHOTS_PATH}")
    raw_lines = FEWSHOTS_PATH.read_text(encoding="utf-8").splitlines()

    # Filter blank lines first so --limit counts actual entries
    lines = [l for l in raw_lines if l.strip()]
    if limit:
        lines = lines[:limit]

    log.info(f"Questions to test: {len(lines)}")

    # ---- Build agent ----
    log.info("Building LangGraph agent ...")
    try:
        graph = await build_graph()
        log.info("Agent built successfully.")
    except Exception as exc:
        log.exception(f"Failed to build agent graph: {exc}")
        sys.exit(1)

    # ---- Run tests ----
    total_time = 0.0
    success_count = 0
    failure_count = 0
    match_count = 0
    results: list[dict] = []

    log.info("-" * 80)

    for idx, line in enumerate(lines, 1):
        try:
            data = json.loads(line)
        except json.JSONDecodeError as exc:
            log.warning(f"[{idx:03d}] Skipping line — JSON decode error: {exc}")
            continue

        qid = data.get("id")
        question = data.get("question")
        ground_truth_sql = data.get("sql", "")

        if not qid or not question:
            log.warning(f"[{idx:03d}] Skipping — missing 'id' or 'question' in: {data}")
            continue

        log.info(f"[{idx:03d}/{len(lines):03d}] ID={qid} | Q: {question[:80]}")

        # ---- Stream the graph ----
        start_time = time.perf_counter()
        generation_time = 0.0
        execution_time = 0.0
        tool_node_count = 0
        last_time = start_time

        try:
            state = {
                "user_query": question,
                "messages": [HumanMessage(content=question)],
                "retrieved_context": [],
                "llm_calls": 0,
                "verify_calls": 0,
                "verified": False,
            }

            async for event in graph.astream(state, stream_mode="updates"):
                now = time.perf_counter()
                step_duration = now - last_time
                last_time = now

                for node_name, update in event.items():
                    for k, v in update.items():
                        if k == "messages":
                            state["messages"].extend(v)
                        else:
                            state[k] = v

                    if node_name == "tool_node":
                        tool_node_count += 1
                        if tool_node_count == 1:
                            generation_time += step_duration
                        else:
                            execution_time += step_duration
                    elif node_name in ("initialize_node", "llm_node"):
                        generation_time += step_duration
                    elif node_name == "verify_node":
                        execution_time += step_duration

            elapsed = time.perf_counter() - start_time
            total_time += elapsed

            if generation_time == 0.0 and execution_time == 0.0:
                generation_time = elapsed

            # ---- Extract result ----
            resp_obj = _extract_sql_and_result(state.get("messages", []))
            generated_sql = resp_obj.sql
            result_rows = resp_obj.result

            # ---- Detect agent-level failure payload ----
            is_failed = False
            error_msg = None
            if result_rows and isinstance(result_rows, list):
                first_row = result_rows[0]
                if isinstance(first_row, dict) and first_row.get("status") == "failed":
                    is_failed = True
                    error_msg = first_row.get("error", "Unknown agent error.")

            # ---- Ground truth comparison ----
            norm_generated = normalize_sql(generated_sql)
            norm_truth = normalize_sql(ground_truth_sql)
            is_match = norm_generated == norm_truth

            if is_failed:
                failure_count += 1
                log.error(
                    f"[{idx:03d}] FAILED  | ID={qid} "
                    f"| Total={elapsed:.2f}s (Gen={generation_time:.2f}s, Exec={execution_time:.2f}s) "
                    f"| Error: {error_msg}"
                )
            else:
                success_count += 1
                match_str = "MATCH" if is_match else "MISMATCH"
                if is_match:
                    match_count += 1
                sql_preview = generated_sql.strip().replace("\n", " ")[:80]
                log.info(
                    f"[{idx:03d}] SUCCESS | ID={qid} "
                    f"| Total={elapsed:.2f}s (Gen={generation_time:.2f}s, Exec={execution_time:.2f}s) "
                    f"| GroundTruth={match_str} "
                    f"| SQL(preview): {sql_preview}..."
                )
                if not is_match:
                    log.debug(
                        f"[{idx:03d}] SQL mismatch details\n"
                        f"  Generated : {norm_generated}\n"
                        f"  GroundTruth: {norm_truth}"
                    )

            results.append(
                {
                    "id": qid,
                    "question": question,
                    "status": "FAILED" if is_failed else "SUCCESS",
                    "time_seconds": elapsed,
                    "generation_time_seconds": generation_time,
                    "execution_time_seconds": execution_time,
                    "matches_ground_truth": is_match,
                    "generated_sql": generated_sql,
                    "ground_truth_sql": ground_truth_sql,
                    "error": error_msg,
                }
            )

        except Exception as exc:
            elapsed = time.perf_counter() - start_time
            failure_count += 1
            log.exception(
                f"[{idx:03d}] EXCEPTION | ID={qid} "
                f"| Time={elapsed:.2f}s | Error: {exc}"
            )
            results.append(
                {
                    "id": qid,
                    "question": question,
                    "status": "EXCEPTION",
                    "time_seconds": elapsed,
                    "generation_time_seconds": elapsed,
                    "execution_time_seconds": 0.0,
                    "matches_ground_truth": False,
                    "generated_sql": "",
                    "ground_truth_sql": ground_truth_sql,
                    "error": str(exc),
                }
            )

    # --------------------------------------------------------------------------
    # Summary
    # --------------------------------------------------------------------------
    total_tested = len(results)
    success_rate = (success_count / total_tested * 100) if total_tested else 0.0
    match_rate = (match_count / total_tested * 100) if total_tested else 0.0
    avg_time = total_time / total_tested if total_tested else 0.0
    all_times = [r["time_seconds"] for r in results]
    min_time = min(all_times) if all_times else 0.0
    max_time = max(all_times) if all_times else 0.0
    total_gen = sum(r.get("generation_time_seconds", 0.0) for r in results)
    total_exec = sum(r.get("execution_time_seconds", 0.0) for r in results)
    avg_gen = total_gen / total_tested if total_tested else 0.0
    avg_exec = total_exec / total_tested if total_tested else 0.0

    log.info("=" * 80)
    log.info("SUMMARY")
    log.info("=" * 80)
    log.info(f"  Total tested          : {total_tested}")
    log.info(f"  Successful            : {success_count}")
    log.info(f"  Failed / Exceptions   : {failure_count}")
    log.info(f"  Success rate          : {success_rate:.2f}%")
    log.info(f"  SQL ground-truth match: {match_count} ({match_rate:.2f}%)")
    log.info(f"  Total wall-clock time : {total_time:.2f}s")
    log.info(f"  Avg time per question : {avg_time:.2f}s")
    log.info(f"  Min / Max time        : {min_time:.2f}s / {max_time:.2f}s")
    log.info(f"  Total Gen / Exec time : {total_gen:.2f}s / {total_exec:.2f}s")
    log.info(f"  Avg   Gen / Exec time : {avg_gen:.2f}s / {avg_exec:.2f}s")

    # Log per-query failure details in the summary block for easy review
    failed_results = [r for r in results if r["status"] in ("FAILED", "EXCEPTION")]
    if failed_results:
        log.info("-" * 80)
        log.info(f"FAILED QUERIES ({len(failed_results)}):")
        for r in failed_results:
            log.error(
                f"  ID={r['id']} | Status={r['status']} "
                f"| Error: {r.get('error') or 'n/a'} "
                f"| Q: {r['question'][:80]}"
            )

    log.info("=" * 80)
    log.info(f"Full log written to: {log_path}")
    log.info("SESSION END")
    log.info("=" * 80)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Test SQL generation against fewshot ground truth."
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        metavar="N",
        help="Only test the first N fewshot entries (e.g. --limit 2 for a quick smoke-test).",
    )
    args = parser.parse_args()

    asyncio.run(test_all_generations(limit=args.limit))
