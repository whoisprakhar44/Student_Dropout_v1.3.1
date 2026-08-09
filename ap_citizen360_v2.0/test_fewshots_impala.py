#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path
from datetime import datetime

# Make sure we can import from the MCP module
BASE_DIR = Path(__file__).resolve().parent
sys.path.append(str(BASE_DIR))

try:
    from MCP.hive_executor import HiveExecutor
except ImportError as e:
    print(f"Error importing HiveExecutor: {e}")
    sys.exit(1)

def main():
    json_path = BASE_DIR / "fewshots_combined.json"
    output_path = BASE_DIR / "impala_fewshot_results.txt"
    
    if not json_path.exists():
        print(f"Error: {json_path} does not exist.")
        sys.exit(1)
        
    print(f"Loading few-shot queries from {json_path}")
    queries = []
    with open(json_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            sql = record.get("sql")
            intent = record.get("intent", "Unknown")
            if sql:
                queries.append({"intent": intent, "sql": sql})
                
    print(f"Loaded {len(queries)} SQL queries.")
    
    print("Connecting to Impala (requires active kinit)...")
    # Enable the execution flag expected by the environment
    os.environ["HIVE_MCP_ENABLED"] = "true"
    
    try:
        executor = HiveExecutor()
        # Optional memory limits for batch execution
        executor._session_settings = [
            "SET MEM_LIMIT=5g",
            "SET DISABLE_CODEGEN=true",
        ]
    except Exception as e:
        print(f"Failed to initialize HiveExecutor: {e}")
        sys.exit(1)
        
    print(f"Writing results to {output_path}")
    success_count = 0
    fail_count = 0
    
    with open(output_path, "w", encoding="utf-8") as out_f:
        out_f.write(f"=== Impala Few-Shot SQL Execution Log ===\n")
        out_f.write(f"Run Date: {datetime.now().isoformat()}\n")
        out_f.write(f"Total Queries: {len(queries)}\n")
        out_f.write("=========================================\n\n")
        
        for idx, q_data in enumerate(queries, 1):
            sql = q_data["sql"]
            intent = q_data["intent"]
            
            print(f"[{idx}/{len(queries)}] Executing SQL for intent: {intent}")
            
            out_f.write(f"--- Query {idx} ({intent}) ---\n")
            out_f.write(f"SQL: {sql}\n")
            
            try:
                # execute() returns a JSON string containing rows or error status
                result_str = executor.execute(sql)
                result_json = json.loads(result_str)
                
                if result_json.get("status") == "success":
                    success_count += 1
                    row_count = result_json.get("row_count", len(result_json.get("rows", [])))
                    out_f.write(f"Status: SUCCESS\n")
                    out_f.write(f"Rows Returned: {row_count}\n")
                else:
                    fail_count += 1
                    out_f.write(f"Status: FAILED\n")
                    out_f.write(f"Error: {result_json.get('error_msg') or result_json.get('error_type')}\n")
                    
            except Exception as e:
                fail_count += 1
                out_f.write(f"Status: FAILED (EXCEPTION)\n")
                out_f.write(f"Error: {e}\n")
                
            out_f.write("\n")
            # flush to see results progressively in case of crash
            out_f.flush()
            
        out_f.write("=========================================\n")
        out_f.write(f"EXECUTION COMPLETE\n")
        out_f.write(f"Successful: {success_count}\n")
        out_f.write(f"Failed:     {fail_count}\n")
        
    print("\nExecution complete.")
    print(f"Success: {success_count} | Failed: {fail_count}")
    print(f"Full log written to: {output_path}")

if __name__ == "__main__":
    main()
