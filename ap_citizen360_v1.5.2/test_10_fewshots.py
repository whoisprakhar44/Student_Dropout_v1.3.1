#!/usr/bin/env python3
import json
import time
import requests
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
BASE_URL = "http://localhost:8000"

def get_fewshot_queries(limit: int = 10):
    json_path = BASE_DIR / "fewshots_combined.json"
    if not json_path.exists():
        print(f"Error: {json_path} does not exist.")
        sys.exit(1)
        
    queries = []
    with open(json_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            question = record.get("question")
            if question:
                queries.append(question)
                if len(queries) >= limit:
                    break
    return queries

def send_query(question: str, idx: int) -> dict:
    payload = {
        "action": "ask",
        "question": question,
        "username": "test_10",
        "session_id": "perf_test_fewshot_single",  # use a single session to test history accumulation
    }
    t0 = time.time()
    try:
        resp = requests.post(f"{BASE_URL}/ask", json=payload, timeout=300)
        elapsed = time.time() - t0
        try:
            data = json.loads(resp.text.strip())
        except Exception:
            data = {"raw": resp.text[:200]}
    except Exception as e:
        elapsed = time.time() - t0
        data = {"error": str(e)}
        
    return {"elapsed": elapsed, "data": data}

if __name__ == "__main__":
    queries = get_fewshot_queries(10)
    
    print("=" * 70)
    print("SEQUENTIAL 10-QUERY FEWSHOT PERFORMANCE TEST")
    print(f"Testing {len(queries)} queries...")
    print("=" * 70)
    
    total_time = 0
    for i, q in enumerate(queries, 1):
        print(f"\n--- Query {i}: {q}")
        result = send_query(q, i)
        elapsed = result["elapsed"]
        total_time += elapsed
        
        data = result["data"]
        
        if "error" in data:
            print(f"    Time:   {elapsed:.1f}s")
            print(f"    Error:  HTTP Request Failed - {data['error']}")
            continue
            
        sql = data.get("sql", "N/A")
        status_info = data.get("result", [{}])
        status = status_info[0].get("status", "ok") if status_info else "N/A"
        error = status_info[0].get("error", "") if status_info else ""
        
        print(f"    Time:   {elapsed:.1f}s")
        print(f"    SQL:    {sql[:120] if sql else 'None'}")
        print(f"    Status: {status}")
        if error:
            print(f"    Error:  {error[:120]}")
    
    print("\n" + "=" * 70)
    print(f"DONE. Total time: {total_time:.1f}s, Average time: {total_time/len(queries):.1f}s")
