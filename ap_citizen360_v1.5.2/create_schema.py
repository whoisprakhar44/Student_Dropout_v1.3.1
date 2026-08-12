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
            
            # Gather all columns defined in doc["columns"] as well as any appended - name: entries
            cols_dict = {}
            for col in doc.get("columns") or []:
                if isinstance(col, dict) and "name" in col:
                    cols_dict[col["name"]] = col.get("type", "TEXT")
            
            # Also catch any appended column definitions in the YAML file
            import re
            appended_matches = re.findall(r'^\s*-\s*name:\s*([a-zA-Z0-9_]+)\s*\n\s*type:\s*([a-zA-Z0-9_]+)', content, re.MULTILINE)
            for col_name, col_type in appended_matches:
                if col_name not in cols_dict:
                    cols_dict[col_name] = col_type

            columns = []
            for name, raw_type in cols_dict.items():
                col_type = _sqlite_type(raw_type)
                suffix = " PRIMARY KEY" if name in primary_key and len(primary_key) == 1 else ""
                columns.append(f'"{name}" {col_type}{suffix}')
                
            cursor.execute(f'DROP TABLE IF EXISTS "{table}"')
            cursor.execute(f'CREATE TABLE "{table}" ({", ".join(columns)})')
            count += 1

    conn.commit()
    conn.close()
    print(f"Created empty database at {path} with {count} tables.")

if __name__ == "__main__":
    create_database()
