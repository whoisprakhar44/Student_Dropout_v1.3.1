import json
import sqlite3
import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
json_path = BASE_DIR / "fewshots_combined.json"
db_path = BASE_DIR / "database" / "schema.db"

def main():
    if not json_path.exists():
        print(f"Error: {json_path} does not exist.")
        return

    print(f"Loading few-shot queries from {json_path}")
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    queries = []
    for record in data:
        sql = record.get("sql")
        intent = record.get("intent", "Unknown")
        if sql:
            # Strip database prefix since SQLite doesn't use it
            sql = sql.replace("ap_citizen360.", "")
            sql = sql.replace("ap_community360.", "")
            sql = sql.replace("curated_datamodels.", "")
            queries.append({"intent": intent, "sql": sql, "original": record.get("sql")})
            
    print(f"Loaded {len(queries)} SQL queries.")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    success = 0
    failed = 0
    empty_results = 0
    
    for idx, q in enumerate(queries, 1):
        try:
            cursor.execute(q["sql"])
            rows = cursor.fetchall()
            success += 1
            if len(rows) == 0:
                empty_results += 1
        except Exception as e:
            failed += 1
            print(f"FAILED query {idx} (Intent: {q['intent']})")
            print(f"Error: {e}")
            print(f"SQL: {q['sql']}\n")
            
    print("=" * 40)
    print("EXECUTION COMPLETE")
    print(f"Successful: {success}")
    print(f"Empty Results (out of successful): {empty_results}")
    print(f"Failed:     {failed}")
    print("=" * 40)

if __name__ == "__main__":
    main()
