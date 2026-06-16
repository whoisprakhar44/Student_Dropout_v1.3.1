#!/usr/bin/env python3
"""
Test script to run all few-shot questions directly through the LangGraph agent,
measuring generation time and success status.
"""

import json
import time
import sys
import asyncio
from pathlib import Path

# Add root directory to python path
ROOT_DIR = Path(__file__).resolve().parent
sys.path.append(str(ROOT_DIR))

# Handle sqlite3 fallback first (same as app.py)
try:
    import pysqlite3
    sys.modules["sqlite3"] = pysqlite3
except ImportError:
    pass

from langchain_core.messages import HumanMessage
from my_agent.agent import build_graph
from app import _extract_sql_and_result

FEWSHOTS_PATH = ROOT_DIR / "school_dropout_fewshots_combined.jsonl"
REPORT_PATH = ROOT_DIR / "generation_test_report.json"

async def test_all_generations():
    if not FEWSHOTS_PATH.is_file():
        print(f"Error: Fewshots file not found at {FEWSHOTS_PATH}")
        sys.exit(1)

    print(f"Reading few-shots from: {FEWSHOTS_PATH}")
    lines = FEWSHOTS_PATH.read_text(encoding="utf-8").splitlines()

    print("Building LangGraph agent...")
    try:
        graph = await build_graph()
        print("Agent built successfully.")
    except Exception as e:
        print(f"Error building agent graph: {e}")
        sys.exit(1)

    results = []
    total_time = 0.0
    success_count = 0
    failure_count = 0

    print("\nStarting generation tests over all fewshots...")
    print("=" * 80)

    for idx, line in enumerate(lines, 1):
        if not line.strip():
            continue

        try:
            data = json.loads(line)
        except json.JSONDecodeError as e:
            print(f"Line {idx}: JSON Decode Error: {e}")
            continue

        qid = data.get("id")
        question = data.get("question")

        if not qid or not question:
            print(f"Line {idx}: Missing 'id' or 'question'")
            continue

        print(f"[{idx:03d}/{len(lines):03d}] ID: {qid} | Question: {question[:60]}...")
        
        # Measure time for generation request
        start_time = time.perf_counter()
        
        try:
            state = await graph.ainvoke(
                {
                    "user_query": question,
                    "messages": [HumanMessage(content=question)],
                    "retrieved_context": [],
                    "llm_calls": 0,
                    "verify_calls": 0,
                    "verified": False,
                }
            )
            elapsed = time.perf_counter() - start_time
            total_time += elapsed

            resp_obj = _extract_sql_and_result(state.get("messages", []))
            generated_sql = resp_obj.sql
            result_rows = resp_obj.result
            
            # Detect failure fallback payload
            is_failed = False
            error_msg = None
            if result_rows and isinstance(result_rows, list):
                first_row = result_rows[0]
                if isinstance(first_row, dict) and first_row.get("status") == "failed":
                    is_failed = True
                    error_msg = first_row.get("error", "Unknown agent error.")

            if is_failed:
                failure_count += 1
                status_str = "FAILED"
                print(f"    -> Result: FAIL | Time: {elapsed:.2f}s | Error: {error_msg}")
            else:
                success_count += 1
                status_str = "SUCCESS"
                print(f"    -> Result: OK   | Time: {elapsed:.2f}s | SQL: {generated_sql.strip().replace(chr(10), ' ')[:50]}...")
            
            results.append({
                "id": qid,
                "question": question,
                "status": status_str,
                "time_seconds": elapsed,
                "generated_sql": generated_sql,
                "error": error_msg
            })

        except Exception as e:
            elapsed = time.perf_counter() - start_time
            failure_count += 1
            print(f"    -> Result: EXCEPTION | Time: {elapsed:.2f}s | Error: {e}")
            results.append({
                "id": qid,
                "question": question,
                "status": "EXCEPTION",
                "time_seconds": elapsed,
                "generated_sql": "",
                "error": str(e)
            })

    # Save detailed report
    report = {
        "summary": {
            "total_tested": len(results),
            "success_count": success_count,
            "failure_count": failure_count,
            "success_rate_pct": (success_count / len(results)) * 100 if results else 0,
            "total_time_seconds": total_time,
            "avg_time_seconds": total_time / len(results) if results else 0,
            "max_time_seconds": max(r["time_seconds"] for r in results) if results else 0,
            "min_time_seconds": min(r["time_seconds"] for r in results) if results else 0,
        },
        "details": results
    }

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print("=" * 80)
    print("\nGeneration Verification Summary:")
    print(f"  Total Questions tested: {report['summary']['total_tested']}")
    print(f"  Success count         : {report['summary']['success_count']}")
    print(f"  Failure count         : {report['summary']['failure_count']}")
    print(f"  Success Rate          : {report['summary']['success_rate_pct']:.2f}%")
    print(f"  Total Time            : {report['summary']['total_time_seconds']:.2f}s")
    print(f"  Avg Time per Question : {report['summary']['avg_time_seconds']:.2f}s")
    print(f"  Min / Max Time        : {report['summary']['min_time_seconds']:.2f}s / {report['summary']['max_time_seconds']:.2f}s")
    print(f"\nDetailed report saved to {REPORT_PATH}")

if __name__ == "__main__":
    asyncio.run(test_all_generations())
