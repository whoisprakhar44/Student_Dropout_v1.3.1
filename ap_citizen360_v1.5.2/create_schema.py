#!/usr/bin/env python3
import os
import sqlite3
import yaml
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
DB_PATH = ROOT_DIR / "database" / "schema.db"
TABLES_DIR = ROOT_DIR / "schema" / "curated_datamodels" / "tables"

def _sqlite_type(source_type: str) -> str:
    t = (source_type or "").upper()
    if any(token in t for token in ("BIGINT", "INT", "BOOLEAN")):
        return "INTEGER"
    if any(token in t for token in ("DECIMAL", "DOUBLE", "FLOAT", "REAL")):
        return "REAL"
    return "TEXT"

def find_columns(node):
    if isinstance(node, dict):
        if "name" in node and "type" in node:
            yield node
        for v in node.values():
            yield from find_columns(v)
    elif isinstance(node, list):
        for item in node:
            yield from find_columns(item)

def create_database(db_path=None, replace=True) -> None:
    path = db_path or DB_PATH
    if replace and os.path.exists(path):
        os.remove(path)

    conn = sqlite3.connect(path)
    cursor = conn.cursor()

    count = 0
    for file_path in sorted(TABLES_DIR.rglob("*.yaml")):
        content = file_path.read_text(encoding="utf-8")
        doc = yaml.safe_load(content)
        if doc and doc.get("table"):
            table = doc["table"]
            primary_key = set(doc.get("primary_key") or [])
            
            cols_dict = {}
            for col in find_columns(doc):
                cols_dict[col["name"]] = col

            columns = []
            for name, col_data in cols_dict.items():
                raw_type = col_data.get("type", "TEXT")
                col_type = _sqlite_type(raw_type)
                suffix = " PRIMARY KEY" if name in primary_key and len(primary_key) == 1 else ""
                
                distinct_vals = col_data.get("distinct")
                if distinct_vals and isinstance(distinct_vals, list):
                    vals = [f"'{str(v).replace(chr(39), chr(39)+chr(39))}'" for v in distinct_vals if str(v).upper() != 'NULL']
                    if vals:
                        suffix += f' CHECK("{name}" IS NULL OR "{name}" IN ({", ".join(vals)}))'
                        
                columns.append(f'"{name}" {col_type}{suffix}')
                
            cursor.execute(f'DROP TABLE IF EXISTS "{table}"')
            cursor.execute(f'CREATE TABLE "{table}" ({", ".join(columns)})')
            count += 1

    conn.commit()
    conn.close()
    print(f"Created empty database at {path} with {count} tables.")

if __name__ == "__main__":
    create_database()
