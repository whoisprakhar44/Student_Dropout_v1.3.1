#!/usr/bin/env python3
"""
Test script to run all few-shot questions directly through the LangGraph agent,
measuring generation time and success status.
"""

import json
import time
import sys
import asyncio
import re
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

def normalize_sql(sql: str) -> str:
    if not sql:
        return ""
    # Remove database prefix "curated_datamodels."
    sql = sql.replace("curated_datamodels.", "")
    # Lowercase
    sql = sql.lower()
    # Normalize whitespaces
    sql = re.sub(r"\s+", " ", sql).strip()
    # Remove optional trailing semicolons or quotes
    sql = sql.rstrip(";").strip()
    return sql

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
    match_count = 0

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
        ground_truth_sql = data.get("sql", "")

        if not qid or not question:
            print(f"Line {idx}: Missing 'id' or 'question'")
            continue

        print(f"[{idx:03d}/{len(lines):03d}] ID: {qid} | Question: {question[:60]}...")
        
        # Measure time for generation request
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
            
            # Stream the steps of the graph to measure node-specific durations
            async for event in graph.astream(state, stream_mode="updates"):
                now = time.perf_counter()
                step_duration = now - last_time
                last_time = now
                
                for node_name, update in event.items():
                    # Merge update into state dictionary
                    for k, v in update.items():
                        if k == "messages":
                            state["messages"].extend(v)
                        else:
                            state[k] = v
                    
                    if node_name == "tool_node":
                        tool_node_count += 1
                        # The first tool_node is RAG schema retrieval (generation phase).
                        # Subsequent tool_nodes run execute_sql (execution phase).
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
            
            # Fallback split if sum of parts is zero
            if generation_time == 0.0 and execution_time == 0.0:
                generation_time = elapsed
                execution_time = 0.0

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

            # Compare generated SQL against ground truth
            norm_generated = normalize_sql(generated_sql)
            norm_truth = normalize_sql(ground_truth_sql)
            is_match = (norm_generated == norm_truth)

            if is_failed:
                failure_count += 1
                status_str = "FAILED"
                print(f"    -> Result: FAIL | Total: {elapsed:.2f}s (Gen: {generation_time:.2f}s, Exec: {execution_time:.2f}s) | Error: {error_msg}")
            else:
                success_count += 1
                status_str = "SUCCESS"
                match_str = "MATCH" if is_match else "MISMATCH"
                if is_match:
                    match_count += 1
                print(f"    -> Result: OK   | Total: {elapsed:.2f}s (Gen: {generation_time:.2f}s, Exec: {execution_time:.2f}s) | Ground Truth: {match_str} | SQL: {generated_sql.strip().replace(chr(10), ' ')[:50]}...")
            
            results.append({
                "id": qid,
                "question": question,
                "status": status_str,
                "time_seconds": elapsed,
                "generation_time_seconds": generation_time,
                "execution_time_seconds": execution_time,
                "matches_ground_truth": is_match,
                "generated_sql": generated_sql,
                "ground_truth_sql": ground_truth_sql,
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
                "generation_time_seconds": elapsed,
                "execution_time_seconds": 0.0,
                "matches_ground_truth": False,
                "generated_sql": "",
                "ground_truth_sql": ground_truth_sql,
                "error": str(e)
            })

    # Save detailed report
    report = {
        "summary": {
            "total_tested": len(results),
            "success_count": success_count,
            "failure_count": failure_count,
            "success_rate_pct": (success_count / len(results)) * 100 if results else 0,
            "match_count": match_count,
            "match_rate_pct": (match_count / len(results)) * 100 if results else 0,
            "total_time_seconds": total_time,
            "avg_time_seconds": total_time / len(results) if results else 0,
            "max_time_seconds": max(r["time_seconds"] for r in results) if results else 0,
            "min_time_seconds": min(r["time_seconds"] for r in results) if results else 0,
            "total_generation_time_seconds": sum(r.get("generation_time_seconds", 0.0) for r in results),
            "avg_generation_time_seconds": sum(r.get("generation_time_seconds", 0.0) for r in results) / len(results) if results else 0,
            "total_execution_time_seconds": sum(r.get("execution_time_seconds", 0.0) for r in results),
            "avg_execution_time_seconds": sum(r.get("execution_time_seconds", 0.0) for r in results) / len(results) if results else 0,
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
    print(f"  SQL Ground Truth Match: {report['summary']['match_count']} ({report['summary']['match_rate_pct']:.2f}%)")
    print(f"  Total Time            : {report['summary']['total_time_seconds']:.2f}s")
    print(f"  Total Gen / Exec Time : {report['summary']['total_generation_time_seconds']:.2f}s / {report['summary']['total_execution_time_seconds']:.2f}s")
    print(f"  Avg Time per Question : {report['summary']['avg_time_seconds']:.2f}s (Gen: {report['summary']['avg_generation_time_seconds']:.2f}s, Exec: {report['summary']['avg_execution_time_seconds']:.2f}s)")
    print(f"  Min / Max Time        : {report['summary']['min_time_seconds']:.2f}s / {report['summary']['max_time_seconds']:.2f}s")
    print(f"\nDetailed report saved to {REPORT_PATH}")

if __name__ == "__main__":
    asyncio.run(test_all_generations())
