#!/usr/bin/env python3
"""
Schema Drift Tracker
====================
Snapshots column metadata from a live database (SQLite or Impala), computes
per-table hashes, compares against the previous snapshot, and auto-updates
YAML schema files when drift is detected.

Usage:
    python schema_drift_tracker.py                   # SQLite mode (default)
    python schema_drift_tracker.py --mode impala      # Impala mode
    python schema_drift_tracker.py --no-update        # snapshot only, skip YAML update
    python schema_drift_tracker.py --force            # overwrite today's snapshot
"""
import argparse
import csv
import hashlib
import io
import json
import os
import re
import sqlite3
import sys
from datetime import date, datetime
from pathlib import Path

import requests
import yaml

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent / ".env")
except ImportError:
    pass  # dotenv not installed — env vars must be set manually

# ── Project paths ─────────────────────────────────────────────────────────────

BASE_DIR = Path(__file__).resolve().parent
TABLES_DIR = BASE_DIR / "schema" / "curated_datamodels" / "tables" / "ap_citizen360"
SNAPSHOTS_DIR = BASE_DIR / "schema_drift_snapshots"
SQLITE_DB = BASE_DIR / "database" / "schema.db"
HIVE_CONFIG = BASE_DIR / "MCP" / "hive_config.yaml"

# Impala type → SQLite type mapping used by create_schema.py — we invert it so
# we can normalise SQLite types back to their canonical Impala equivalents when
# comparing against YAMLs.
_SQLITE_TO_CANONICAL = {
    "TEXT": "STRING",
    "INTEGER": "INT",       # covers BIGINT, INT, BOOLEAN
    "REAL": "DOUBLE",       # covers DECIMAL, DOUBLE, FLOAT
}


# ── YAML helpers ──────────────────────────────────────────────────────────────

def load_yaml_tables() -> list[dict]:
    """Return a list of parsed YAML dicts for every table definition."""
    tables = []
    for yaml_path in sorted(TABLES_DIR.glob("*.yaml")):
        doc = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
        if doc and doc.get("table") and doc.get("columns"):
            doc["_yaml_path"] = str(yaml_path)
            tables.append(doc)
    return tables


# ── Database backends ─────────────────────────────────────────────────────────

def _describe_sqlite(table_name: str) -> list[dict]:
    """Use PRAGMA table_info to get column metadata from schema.db."""
    if not SQLITE_DB.exists():
        raise FileNotFoundError(f"SQLite database not found: {SQLITE_DB}")

    conn = sqlite3.connect(str(SQLITE_DB))
    cursor = conn.cursor()
    cursor.execute(f'PRAGMA table_info("{table_name}")')
    rows = cursor.fetchall()
    conn.close()

    # PRAGMA table_info returns: (cid, name, type, notnull, dflt_value, pk)
    columns = []
    for row in rows:
        columns.append({
            "column_name": row[1],
            "type": row[2] or "TEXT",
            "nullable": "false" if row[3] else "true",
        })
    return columns


def _describe_impala(executor, database: str, table_name: str) -> list[dict]:
    """Use DESCRIBE to get column metadata from Impala via HiveExecutor."""
    query = f"DESCRIBE {database}.{table_name}"
    result_json = executor.execute(query)
    payload = json.loads(result_json)

    if payload.get("status") != "success":
        raise RuntimeError(
            f"DESCRIBE failed for {database}.{table_name}: "
            f"{payload.get('error_msg', 'unknown error')}"
        )

    columns = []
    for row in payload.get("rows", []):
        # Impala DESCRIBE returns: name, type, comment
        col_name = row.get("name", row.get("col_name", "")).strip()
        col_type = row.get("type", row.get("data_type", "")).strip()

        # Skip empty rows and partition headers
        if not col_name or col_name.startswith("#") or col_name.startswith("---"):
            continue

        # Impala doesn't directly report nullable in DESCRIBE, default to true
        nullable = "true"

        columns.append({
            "column_name": col_name,
            "type": col_type.upper(),
            "nullable": nullable,
        })
    return columns


# ── Snapshot logic ────────────────────────────────────────────────────────────

def _csv_content(columns: list[dict]) -> str:
    """Produce a deterministic CSV string from column metadata."""
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(["column_name", "type", "nullable"])
    for col in sorted(columns, key=lambda c: c["column_name"]):
        writer.writerow([col["column_name"], col["type"], col["nullable"]])
    return buf.getvalue()


def _hash_content(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _find_previous_snapshot(today_str: str) -> str | None:
    """Find the most recent snapshot folder before today_str."""
    if not SNAPSHOTS_DIR.exists():
        return None

    dated_dirs = []
    for d in SNAPSHOTS_DIR.iterdir():
        if d.is_dir() and re.match(r"^\d{4}-\d{2}-\d{2}$", d.name):
            if d.name < today_str:
                dated_dirs.append(d.name)
    if not dated_dirs:
        return None
    return sorted(dated_dirs)[-1]


def _load_previous_hashes(prev_dir: Path) -> dict[str, str]:
    """Load prev_hash values from a previous snapshot's _drift_summary.csv."""
    summary_path = prev_dir / "_drift_summary.csv"
    hashes = {}

    # If a summary exists, use cur_hash from it
    if summary_path.exists():
        with open(summary_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                hashes[row["table_name"]] = row["cur_hash"]
        return hashes

    # Fallback: compute hashes from the per-table CSVs in that folder
    for csv_path in prev_dir.glob("*.csv"):
        if csv_path.name.startswith("_"):
            continue
        table_name = csv_path.stem
        content = csv_path.read_text(encoding="utf-8")
        hashes[table_name] = _hash_content(content)
    return hashes


# ── YAML auto-updater ─────────────────────────────────────────────────────────

def _update_yaml(yaml_path: str, live_columns: list[dict], mode: str) -> dict:
    """
    Update a YAML file's columns list to match live database metadata.
    Preserves existing descriptions, distinct values, and other column metadata.

    Returns a dict describing changes made: {added: [...], removed: [...], changed: [...]}.
    """
    raw_text = Path(yaml_path).read_text(encoding="utf-8")
    doc = yaml.safe_load(raw_text)

    if not doc or "columns" not in doc:
        return {"added": [], "removed": [], "changed": []}

    # Build lookup from existing YAML columns
    yaml_cols_by_name = {}
    for col in doc["columns"]:
        yaml_cols_by_name[col["name"].lower()] = col

    # Build lookup from live database
    live_cols_by_name = {}
    for col in live_columns:
        live_cols_by_name[col["column_name"].lower()] = col

    changes = {"added": [], "removed": [], "changed": []}

    # Determine type mapping based on mode
    type_normaliser = _SQLITE_TO_CANONICAL if mode == "sqlite" else {}

    # 1. Update existing columns and detect type/nullable changes
    new_columns = []
    for col in doc["columns"]:
        col_name_lower = col["name"].lower()
        if col_name_lower in live_cols_by_name:
            live = live_cols_by_name[col_name_lower]
            live_type = live["type"]
            canonical_type = type_normaliser.get(live_type, live_type)

            changed_fields = []

            # Check type change
            if col.get("type", "").upper() != canonical_type.upper():
                changed_fields.append(
                    f"type: {col.get('type')} → {canonical_type}"
                )
                col["type"] = canonical_type

            # Check nullable change
            live_nullable = live["nullable"].lower() == "true"
            yaml_nullable = col.get("nullable", True)
            if isinstance(yaml_nullable, str):
                yaml_nullable = yaml_nullable.lower() == "true"
            if yaml_nullable != live_nullable:
                changed_fields.append(
                    f"nullable: {yaml_nullable} → {live_nullable}"
                )
                col["nullable"] = live_nullable

            if changed_fields:
                changes["changed"].append(
                    f"{col['name']} ({', '.join(changed_fields)})"
                )
            new_columns.append(col)
        else:
            # Column removed from live database
            changes["removed"].append(col["name"])
            # Don't add to new_columns — it's gone

    # 2. Add new columns from live database
    existing_names = {c["name"].lower() for c in new_columns}
    for col in live_columns:
        col_name_lower = col["column_name"].lower()
        if col_name_lower not in existing_names:
            live_type = col["type"]
            canonical_type = type_normaliser.get(live_type, live_type)
            live_nullable = col["nullable"].lower() == "true"

            new_col = {
                "name": col["column_name"],
                "type": canonical_type,
                "nullable": live_nullable,
                "description": "",
            }
            new_columns.append(new_col)
            changes["added"].append(col["column_name"])

    # 3. Write updated YAML only if there are changes
    if changes["added"] or changes["removed"] or changes["changed"]:
        doc["columns"] = new_columns
        with open(yaml_path, "w", encoding="utf-8") as f:
            yaml.dump(doc, f, default_flow_style=False, allow_unicode=True,
                      sort_keys=False, width=120)

    return changes


# ── Distinct value fetching (no LLM) ─────────────────────────────────────────

def _fetch_distinct_sqlite(table_name: str, column_name: str, limit: int = 51) -> list[str]:
    """Fetch distinct values for a column from SQLite."""
    conn = sqlite3.connect(str(SQLITE_DB))
    cursor = conn.cursor()
    try:
        cursor.execute(
            f'SELECT DISTINCT "{column_name}" FROM "{table_name}" '
            f'WHERE "{column_name}" IS NOT NULL LIMIT {limit}'
        )
        values = [str(row[0]) for row in cursor.fetchall() if row[0] is not None]
    except Exception:
        values = []
    finally:
        conn.close()
    return values


def _fetch_distinct_impala(
    executor, database: str, table_name: str, column_name: str, limit: int = 51
) -> list[str]:
    """Fetch distinct values for a column from Impala via HiveExecutor."""
    query = (
        f"SELECT {column_name}, COUNT(*) as cnt "
        f"FROM {database}.{table_name} "
        f"WHERE {column_name} IS NOT NULL "
        f"GROUP BY {column_name} ORDER BY cnt DESC LIMIT {limit}"
    )
    try:
        result_json = executor.execute(query)
        payload = json.loads(result_json)
        if payload.get("status") == "success":
            return [
                str(row.get(column_name, row.get(column_name.lower(), "")))
                for row in payload.get("rows", [])
                if row.get(column_name, row.get(column_name.lower())) is not None
            ]
    except Exception:
        pass
    return []


def _fetch_distinct_values(
    table_name: str, column_name: str, mode: str,
    executor=None, database: str = "ap_citizen360", limit: int = 51,
) -> list[str]:
    """Fetch distinct values from the appropriate backend."""
    if mode == "sqlite":
        return _fetch_distinct_sqlite(table_name, column_name, limit)
    else:
        return _fetch_distinct_impala(executor, database, table_name, column_name, limit)


# ── LLM description generation (Ollama) ──────────────────────────────────────

def _ollama_base_url() -> str:
    return os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")


def _ollama_model() -> str:
    return os.getenv("OLLAMA_CHAT_MODEL", "qwen3.5:0.8b-mlx")


def _call_ollama(prompt: str, timeout: int = 60) -> str:
    """Call Ollama chat completion API and return the response text."""
    url = f"{_ollama_base_url()}/api/generate"
    payload = {
        "model": _ollama_model(),
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.3,
            "num_predict": 1024,
        },
    }
    try:
        resp = requests.post(url, json=payload, timeout=timeout)
        resp.raise_for_status()
        return resp.json().get("response", "").strip()
    except Exception as e:
        return f"[LLM error: {e}]"


def _llm_enrich_yaml(
    yaml_path: str,
    added_columns: list[str],
    changed_columns: list[str],
    distinct_map: dict[str, list[str]],
) -> dict:
    """
    Call the local Ollama model to generate BIRD-style descriptions for
    new/changed columns and update table-level fields (relationships,
    business_terms, common_operations).

    Returns a dict of what was enriched.
    """
    doc = yaml.safe_load(Path(yaml_path).read_text(encoding="utf-8"))
    if not doc:
        return {"descriptions": [], "table_fields": []}

    table_name = doc.get("table", "")
    table_desc = doc.get("description", "")

    # Build context: existing columns with descriptions (as examples)
    existing_examples = []
    for col in doc.get("columns", []):
        if col.get("description"):
            existing_examples.append(
                f"  - {col['name']} ({col.get('type', 'STRING')}): "
                f"{col['description']}"
            )
    examples_str = "\n".join(existing_examples[:8])  # show up to 8 examples

    # Build the list of columns needing descriptions
    cols_needing_desc = []
    for col in doc.get("columns", []):
        if col["name"] in added_columns or col["name"] in changed_columns:
            distinct_vals = distinct_map.get(col["name"], [])
            distinct_str = ", ".join(f"'{v}'" for v in distinct_vals[:5]) if distinct_vals else ""
            cols_needing_desc.append({
                "name": col["name"],
                "type": col.get("type", "STRING"),
                "distinct": distinct_str,
                "current_desc": col.get("description", ""),
            })

    if not cols_needing_desc:
        return {"descriptions": [], "table_fields": []}

    # Build the columns block for the prompt
    cols_block = ""
    for c in cols_needing_desc:
        line = f"  - {c['name']} (type: {c['type']})"
        if c["distinct"]:
            line += f" [sample values: {c['distinct']}]"
        if c["current_desc"]:
            line += f" [hint: {c['current_desc']}]"
        cols_block += line + "\n"

    # Existing relationships and business terms for context
    existing_rels = doc.get("relationships", [])
    existing_terms = doc.get("business_terms", [])
    existing_ops = doc.get("common_operations", [])

    prompt = f"""You are a data catalog assistant for the AP Citizen360 government database.
Table: {table_name}
Table description: {table_desc}

Existing column descriptions (use the same style):
{examples_str}

Existing relationships: {json.dumps(existing_rels)}
Existing business_terms: {json.dumps(existing_terms)}
Existing common_operations: {json.dumps(existing_ops)}

New/changed columns that need descriptions:
{cols_block}
For each column above, write a concise 1-line description in the same style as the existing examples.
For columns ending in _id, note if they are likely a Foreign Key referencing another dim_/fact_ table.
For categorical STRING columns with sample values, mention "Categorical column. Distinct values: ..." in the description.

Also, if any new column ending in _id suggests a new relationship or join, output an updated relationships list.
If any new column introduces a new domain concept, output updated business_terms.
If any new column enables new query patterns, output updated common_operations.

Respond ONLY in this exact YAML format (no extra text, no markdown fences):
column_descriptions:
  column_name_1: "description here"
  column_name_2: "description here"
new_relationships:
  - "table.col is a foreign key to other_table.col."
new_business_terms:
  - "term"
new_common_operations:
  - "operation description"

If there are no new relationships/terms/operations, output empty lists [].
"""

    raw_response = _call_ollama(prompt)

    # Parse the LLM response as YAML
    enriched = {"descriptions": [], "table_fields": []}
    try:
        # Strip any markdown code fences the model might add
        cleaned = re.sub(r"```ya?ml\s*", "", raw_response)
        cleaned = re.sub(r"```\s*", "", cleaned)
        # Strip any leading <think>...</think> reasoning blocks
        cleaned = re.sub(r"<think>.*?</think>", "", cleaned, flags=re.DOTALL).strip()
        parsed = yaml.safe_load(cleaned)
        if not isinstance(parsed, dict):
            parsed = {}
    except Exception:
        parsed = {}

    # Apply column descriptions
    col_descs = parsed.get("column_descriptions", {})
    if isinstance(col_descs, dict):
        col_lookup = {c["name"]: c for c in doc.get("columns", [])}
        for col_name, desc in col_descs.items():
            if col_name in col_lookup and isinstance(desc, str) and desc:
                col_lookup[col_name]["description"] = desc
                enriched["descriptions"].append(col_name)

    # Apply new relationships
    new_rels = parsed.get("new_relationships", [])
    if isinstance(new_rels, list) and new_rels:
        current_rels = doc.get("relationships", []) or []
        for rel in new_rels:
            if isinstance(rel, str) and rel not in current_rels:
                current_rels.append(rel)
        doc["relationships"] = current_rels
        enriched["table_fields"].append("relationships")

    # Apply new business terms
    new_terms = parsed.get("new_business_terms", [])
    if isinstance(new_terms, list) and new_terms:
        current_terms = doc.get("business_terms", []) or []
        for term in new_terms:
            if isinstance(term, str) and term not in current_terms:
                current_terms.append(term)
        doc["business_terms"] = current_terms
        enriched["table_fields"].append("business_terms")

    # Apply new common operations
    new_ops = parsed.get("new_common_operations", [])
    if isinstance(new_ops, list) and new_ops:
        current_ops = doc.get("common_operations", []) or []
        for op in new_ops:
            if isinstance(op, str) and op not in current_ops:
                current_ops.append(op)
        doc["common_operations"] = current_ops
        enriched["table_fields"].append("common_operations")

    # Write back
    if enriched["descriptions"] or enriched["table_fields"]:
        with open(yaml_path, "w", encoding="utf-8") as f:
            yaml.dump(doc, f, default_flow_style=False, allow_unicode=True,
                      sort_keys=False, width=120)

    return enriched


# ── Column diff for reporting ─────────────────────────────────────────────────

def _diff_columns(prev_csv_path: Path, cur_csv_path: Path) -> dict:
    """Compare two per-table CSVs and return added/removed/changed columns."""
    def _parse_csv(path: Path) -> dict[str, dict]:
        cols = {}
        with open(path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                cols[row["column_name"]] = {
                    "type": row["type"],
                    "nullable": row["nullable"],
                }
        return cols

    prev_cols = _parse_csv(prev_csv_path)
    cur_cols = _parse_csv(cur_csv_path)

    prev_names = set(prev_cols.keys())
    cur_names = set(cur_cols.keys())

    added = sorted(cur_names - prev_names)
    removed = sorted(prev_names - cur_names)

    changed = []
    for name in sorted(prev_names & cur_names):
        diffs = []
        if prev_cols[name]["type"] != cur_cols[name]["type"]:
            diffs.append(f"type: {prev_cols[name]['type']} → {cur_cols[name]['type']}")
        if prev_cols[name]["nullable"] != cur_cols[name]["nullable"]:
            diffs.append(
                f"nullable: {prev_cols[name]['nullable']} → {cur_cols[name]['nullable']}"
            )
        if diffs:
            changed.append(f"{name} ({', '.join(diffs)})")

    return {"added": added, "removed": removed, "changed": changed}


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Schema drift tracker — snapshots column metadata and detects drift."
    )
    parser.add_argument(
        "--mode", choices=["sqlite", "impala"], default="sqlite",
        help="Database backend to use (default: sqlite)",
    )
    parser.add_argument(
        "--no-update", action="store_true",
        help="Snapshot only — do not auto-update YAML files",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Overwrite today's snapshot if it already exists",
    )
    args = parser.parse_args()

    # ── 1. Load YAML definitions ──────────────────────────────────────────────
    yaml_tables = load_yaml_tables()
    if not yaml_tables:
        print("❌ No YAML table definitions found.")
        sys.exit(1)

    print(f"📋 Found {len(yaml_tables)} table definitions in YAML schemas")

    # ── 2. Prepare dated snapshot folder ──────────────────────────────────────
    today_str = date.today().isoformat()
    snapshot_dir = SNAPSHOTS_DIR / today_str
    if snapshot_dir.exists() and not args.force:
        print(f"⚠️  Snapshot for {today_str} already exists. Use --force to overwrite.")
        sys.exit(0)
    snapshot_dir.mkdir(parents=True, exist_ok=True)

    # ── 3. Connect to database ────────────────────────────────────────────────
    executor = None
    if args.mode == "impala":
        mcp_path = BASE_DIR / "MCP"
        sys.path.insert(0, str(mcp_path))
        try:
            from hive_executor import HiveExecutor
        except ImportError as e:
            print(f"❌ Could not import HiveExecutor: {e}")
            sys.exit(1)

        os.environ["HIVE_MCP_ENABLED"] = "true"
        try:
            executor = HiveExecutor(str(HIVE_CONFIG))
            print("✅ Connected to Impala")
        except Exception as e:
            print(f"❌ Failed to connect to Impala: {e}")
            sys.exit(1)
    else:
        if not SQLITE_DB.exists():
            print(f"❌ SQLite database not found at: {SQLITE_DB}")
            print("   Run `python create_schema.py` first to create it.")
            sys.exit(1)
        print(f"✅ Using SQLite database: {SQLITE_DB.name}")

    # ── 4. Snapshot each table ────────────────────────────────────────────────
    current_hashes = {}
    table_columns = {}  # table_name → list of column dicts (for YAML update)
    errors = []

    for doc in yaml_tables:
        table_name = doc["table"]
        database = doc.get("database", "ap_citizen360")

        try:
            if args.mode == "sqlite":
                columns = _describe_sqlite(table_name)
            else:
                columns = _describe_impala(executor, database, table_name)

            if not columns:
                errors.append((table_name, "No columns returned"))
                continue

            # Write per-table CSV
            csv_content = _csv_content(columns)
            csv_path = snapshot_dir / f"{table_name}.csv"
            csv_path.write_text(csv_content, encoding="utf-8")

            current_hashes[table_name] = _hash_content(csv_content)
            table_columns[table_name] = columns

        except Exception as e:
            errors.append((table_name, str(e)))
            print(f"  ⚠️  {table_name}: {e}")

    print(f"📸 Snapshotted {len(current_hashes)} tables to {snapshot_dir.name}/")

    # ── 5. Load previous snapshot hashes ──────────────────────────────────────
    prev_date = _find_previous_snapshot(today_str)
    prev_hashes = {}
    if prev_date:
        prev_dir = SNAPSHOTS_DIR / prev_date
        prev_hashes = _load_previous_hashes(prev_dir)
        print(f"📂 Previous snapshot: {prev_date} ({len(prev_hashes)} tables)")
    else:
        print("📂 No previous snapshot found — all tables will be marked NEW")

    # ── 6. Build drift summary ────────────────────────────────────────────────
    all_tables = sorted(set(list(current_hashes.keys()) + list(prev_hashes.keys())))
    summary_rows = []
    changed_tables = []

    for table_name in all_tables:
        cur_hash = current_hashes.get(table_name, "")
        prev_hash = prev_hashes.get(table_name, "")

        if cur_hash and not prev_hash:
            status = "NEW"
        elif prev_hash and not cur_hash:
            status = "REMOVED"
        elif cur_hash == prev_hash:
            status = "UNCHANGED"
        else:
            status = "CHANGED"
            changed_tables.append(table_name)

        summary_rows.append({
            "table_name": table_name,
            "prev_hash": prev_hash,
            "cur_hash": cur_hash,
            "status": status,
        })

    # Write _drift_summary.csv
    summary_path = snapshot_dir / "_drift_summary.csv"
    with open(summary_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f, fieldnames=["table_name", "prev_hash", "cur_hash", "status"]
        )
        writer.writeheader()
        writer.writerows(summary_rows)

    # ── 7. Print drift report ─────────────────────────────────────────────────
    n_unchanged = sum(1 for r in summary_rows if r["status"] == "UNCHANGED")
    n_new = sum(1 for r in summary_rows if r["status"] == "NEW")
    n_removed = sum(1 for r in summary_rows if r["status"] == "REMOVED")
    n_changed = len(changed_tables)

    print()
    print("=" * 70)
    print(f"  SCHEMA DRIFT REPORT — {today_str}")
    print("=" * 70)
    print(f"  UNCHANGED : {n_unchanged}")
    print(f"  NEW       : {n_new}")
    print(f"  CHANGED   : {n_changed}")
    print(f"  REMOVED   : {n_removed}")
    if errors:
        print(f"  ERRORS    : {len(errors)}")
    print("=" * 70)

    # Show detailed diff for changed tables
    if changed_tables and prev_date:
        prev_dir = SNAPSHOTS_DIR / prev_date
        print()
        for table_name in changed_tables:
            prev_csv = prev_dir / f"{table_name}.csv"
            cur_csv = snapshot_dir / f"{table_name}.csv"

            print(f"  📊 {table_name}:")
            if prev_csv.exists() and cur_csv.exists():
                diff = _diff_columns(prev_csv, cur_csv)
                if diff["added"]:
                    for col in diff["added"]:
                        print(f"    ＋ {col}")
                if diff["removed"]:
                    for col in diff["removed"]:
                        print(f"    － {col}")
                if diff["changed"]:
                    for change in diff["changed"]:
                        print(f"    ⚡ {change}")
            else:
                print("    (cannot diff — previous CSV missing)")
            print()

    # ── 8. Auto-update YAMLs ──────────────────────────────────────────────────
    if not args.no_update and changed_tables:
        print("─" * 70)
        print("  AUTO-UPDATING YAML FILES")
        print("─" * 70)

        yaml_by_table = {doc["table"]: doc for doc in yaml_tables}

        for table_name in changed_tables:
            doc = yaml_by_table.get(table_name)
            if not doc or table_name not in table_columns:
                continue

            yaml_path = doc["_yaml_path"]
            database = doc.get("database", "ap_citizen360")
            live_cols = table_columns[table_name]
            changes = _update_yaml(yaml_path, live_cols, args.mode)

            if changes["added"] or changes["removed"] or changes["changed"]:
                print(f"\n  ✏️  {Path(yaml_path).name}:")
                for col in changes["added"]:
                    print(f"    ＋ added column: {col}")
                for col in changes["removed"]:
                    print(f"    － removed column: {col}")
                for change in changes["changed"]:
                    print(f"    ⚡ updated: {change}")

                # ── 8a. Fetch distinct values for new STRING columns ──────
                distinct_map = {}
                desc_hints = {}
                string_cols = []
                # Identify which new/changed columns are STRING type
                updated_doc = yaml.safe_load(
                    Path(yaml_path).read_text(encoding="utf-8")
                )
                for col in updated_doc.get("columns", []):
                    if col["name"] in changes["added"]:
                        col_type = col.get("type", "").upper()
                        if col_type in ("STRING", "TEXT"):
                            string_cols.append(col["name"])

                if string_cols:
                    print(f"    📊 Fetching distinct values for {len(string_cols)} STRING column(s)...")
                    
                    uuid_pattern = re.compile(
                        r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', 
                        re.IGNORECASE
                    )
                    
                    for col_name in string_cols:
                        vals = _fetch_distinct_values(
                            table_name, col_name, args.mode,
                            executor=executor, database=database,
                        )
                        if vals:
                            if len(vals) > 50:
                                desc_hints[col_name] = "High cardinality value."
                                print(f"       {col_name}: Discarded distinct list (>50 values)")
                            else:
                                is_uuid = all(uuid_pattern.match(v) for v in vals)
                                is_numeric = all(v.replace('.', '', 1).replace('-', '', 1).isdigit() for v in vals)
                                
                                if is_uuid:
                                    desc_hints[col_name] = "UUID identifier."
                                    print(f"       {col_name}: Discarded distinct list (UUIDs detected)")
                                elif is_numeric:
                                    desc_hints[col_name] = "Continuous numeric value."
                                    print(f"       {col_name}: Discarded distinct list (Continuous values detected)")
                                else:
                                    distinct_map[col_name] = vals
                                    print(f"       {col_name}: {vals[:5]} (Total: {len(vals)})")

                    # Write distinct values and hints into the YAML
                    if distinct_map or desc_hints:
                        doc_for_distinct = yaml.safe_load(
                            Path(yaml_path).read_text(encoding="utf-8")
                        )
                        for col in doc_for_distinct.get("columns", []):
                            if col["name"] in distinct_map:
                                col["distinct"] = distinct_map[col["name"]]
                            if col["name"] in desc_hints:
                                col["description"] = desc_hints[col["name"]]
                        with open(yaml_path, "w", encoding="utf-8") as f:
                            yaml.dump(
                                doc_for_distinct, f,
                                default_flow_style=False,
                                allow_unicode=True,
                                sort_keys=False, width=120,
                            )

                # ── 8b. LLM enrichment for descriptions & table fields ────
                all_drift_cols = changes["added"] + [
                    c.split(" (")[0] for c in changes["changed"]
                ]
                if all_drift_cols:
                    print(f"    🤖 Generating descriptions via Ollama ({_ollama_model()})...")
                    enriched = _llm_enrich_yaml(
                        yaml_path, changes["added"],
                        [c.split(" (")[0] for c in changes["changed"]],
                        distinct_map,
                    )
                    if enriched["descriptions"]:
                        for col_name in enriched["descriptions"]:
                            print(f"       ✍️  {col_name}: description generated")
                    if enriched["table_fields"]:
                        for field in enriched["table_fields"]:
                            print(f"       📝 {field} updated")
                    if not enriched["descriptions"] and not enriched["table_fields"]:
                        print("       ⚠️  LLM returned no usable enrichment")

            else:
                print(f"  ✓ {Path(yaml_path).name}: no structural change (hash diff was cosmetic)")

        print()
    elif args.no_update and changed_tables:
        print("\n  ℹ️  --no-update specified: YAML files were NOT modified.")

    # ── 9. New tables (in DB but no YAML) ─────────────────────────────────────
    for table_name in all_tables:
        row = next((r for r in summary_rows if r["table_name"] == table_name), None)
        if row and row["status"] == "NEW" and not prev_hashes:
            # First run, all are "NEW" — don't spam the output
            pass

    # ── 10. Errors ────────────────────────────────────────────────────────────
    if errors:
        print("  ⚠️  Tables with errors:")
        for table_name, err in errors:
            print(f"    - {table_name}: {err}")
        print()

    # ── 11. Cleanup ───────────────────────────────────────────────────────────
    if executor:
        executor.close()

    print(f"✅ Snapshot saved to: {snapshot_dir}")
    print(f"   Summary: {summary_path.name}")
    print(f"   Per-table CSVs: {len(current_hashes)} files")


if __name__ == "__main__":
    main()
