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
        doc = yaml.safe_load(file_path.read_text(encoding="utf-8"))
        if doc and doc.get("table") and doc.get("columns"):
            table = doc["table"]
            columns = []
            primary_key = set(doc.get("primary_key") or [])
            for col in doc["columns"]:
                name = col["name"]
                col_type = _sqlite_type(col.get("type", "TEXT"))
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
