#!/usr/bin/env python3
"""
Verify all few-shot SQL queries.
Supports running against SQLite (default) or the production Impala cluster (via --impala).
"""

import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path

# Paths
ROOT_DIR = Path(__file__).resolve().parent
FEWSHOTS_PATH = ROOT_DIR / "school_dropout_fewshots_200.jsonl"
DB_PATH = ROOT_DIR / "database" / "schema.db"
MCP_DIR = ROOT_DIR / "MCP"

def main():
    parser = argparse.ArgumentParser(description="Verify all few-shot SQL queries.")
    parser.add_argument(
        "--impala",
        action="store_true",
        help="Run queries against production Impala cluster instead of SQLite"
    )
    args = parser.parse_args()

    if not FEWSHOTS_PATH.is_file():
        print(f"Error: fewshots file not found at {FEWSHOTS_PATH}")
        sys.exit(1)

    print(f"Loading few-shots from: {FEWSHOTS_PATH}")
    lines = FEWSHOTS_PATH.read_text(encoding="utf-8").splitlines()

    total = 0
    passed = 0
    failed = 0

    if args.impala:
        print("Running in IMPALA mode.")
        # Insert MCP path into sys.path to import HiveExecutor
        if str(MCP_DIR) not in sys.path:
            sys.path.insert(0, str(MCP_DIR))
        
        try:
            from hive_executor import HiveExecutor
        except ImportError as e:
            print(f"Error importing HiveExecutor: {e}. Make sure you run inside the virtualenv and dependencies are installed.")
            sys.exit(1)

        config_path = MCP_DIR / "hive_config.yaml"
        if not config_path.is_file():
            print(f"Error: hive_config.yaml not found at {config_path}")
            sys.exit(1)

        print("Initializing HiveExecutor (Impala)...")
        # Ensure HIVE_MCP_ENABLED is set to allow initialization if needed
        os.environ["HIVE_MCP_ENABLED"] = "true"
        try:
            executor = HiveExecutor(str(config_path))
        except Exception as e:
            print(f"Error initializing connection to Impala: {e}")
            sys.exit(1)

        for idx, line in enumerate(lines, 1):
            if not line.strip():
                continue

            try:
                data = json.loads(line)
            except json.JSONDecodeError as e:
                print(f"Line {idx}: JSON Decode Error: {e}")
                continue

            qid = data.get("id")
            sql = data.get("sql")

            if not qid or not sql:
                print(f"Line {idx}: Missing 'id' or 'sql'")
                continue

            total += 1

            # In Impala mode, execute query verbatim (with curated_datamodels. prefix)
            try:
                res_str = executor.execute(sql)
                res = json.loads(res_str)
                if res.get("status") == "success":
                    passed += 1
                    # print(f"[OK] {qid}")
                else:
                    failed += 1
                    print(f"\n[FAIL] {qid}")
                    print(f"Question: {data.get('question')}")
                    print(f"Error: {res.get('error_msg')}")
                    print("SQL Query executed:")
                    print(sql)
                    print("-" * 60)
            except Exception as e:
                failed += 1
                print(f"\n[FAIL] {qid}")
                print(f"Question: {data.get('question')}")
                print(f"Exception during execution: {e}")
                print("SQL Query executed:")
                print(sql)
                print("-" * 60)

        executor.close()

    else:
        print("Running in SQLITE mode (default).")
        if not DB_PATH.is_file():
            print(f"Error: database not found at {DB_PATH}. Please run create_schema.py first.")
            sys.exit(1)

        print(f"Connecting to SQLite database: {DB_PATH}")
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        for idx, line in enumerate(lines, 1):
            if not line.strip():
                continue

            try:
                data = json.loads(line)
            except json.JSONDecodeError as e:
                print(f"Line {idx}: JSON Decode Error: {e}")
                continue

            qid = data.get("id")
            sql = data.get("sql")

            if not qid or not sql:
                print(f"Line {idx}: Missing 'id' or 'sql'")
                continue

            total += 1

            # Clean SQL for SQLite
            # Remove 'curated_datamodels.' catalog/schema prefix
            clean_sql = sql.replace("curated_datamodels.", "")

            try:
                cursor.execute(clean_sql)
                cursor.fetchall()
                passed += 1
                # print(f"[OK] {qid}")
            except Exception as e:
                failed += 1
                print(f"\n[FAIL] {qid}")
                print(f"Question: {data.get('question')}")
                print(f"Error: {e}")
                print("SQL Query executed:")
                print(clean_sql)
                print("-" * 60)

        conn.close()

    print("\n" + "=" * 40)
    print("Verification Summary:")
    print(f"Total SQL Queries Checked : {total}")
    print(f"Passed                    : {passed}")
    print(f"Failed                    : {failed}")
    print("=" * 40)

    if failed > 0:
        sys.exit(1)
    else:
        sys.exit(0)

if __name__ == "__main__":
    main()
