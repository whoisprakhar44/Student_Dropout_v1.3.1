#!/usr/bin/env python3
"""
Verify all few-shot SQL queries against the local SQLite database.
Strips the 'curated_datamodels.' schema prefix to run on SQLite.
"""

import json
import sqlite3
import sys
from pathlib import Path

# Paths
ROOT_DIR = Path(__file__).resolve().parent
FEWSHOTS_PATH = ROOT_DIR / "school_dropout_fewshots_200.jsonl"
DB_PATH = ROOT_DIR / "database" / "schema.db"

def main():
    if not FEWSHOTS_PATH.is_file():
        print(f"Error: fewshots file not found at {FEWSHOTS_PATH}")
        sys.exit(1)
        
    if not DB_PATH.is_file():
        print(f"Error: database not found at {DB_PATH}. Please run create_schema.py first.")
        sys.exit(1)
        
    print(f"Connecting to database: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print(f"Loading few-shots from: {FEWSHOTS_PATH}")
    lines = FEWSHOTS_PATH.read_text(encoding="utf-8").splitlines()
    
    total = 0
    passed = 0
    failed = 0
    
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
            # Try fetching to ensure execution completes fully
            cursor.fetchall()
            passed += 1
            # Optional: print OK for progress
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
