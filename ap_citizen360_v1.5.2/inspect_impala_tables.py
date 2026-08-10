#!/usr/bin/env python3
import os
import sys
import json
import re
from pathlib import Path

# Add MCP folder to path to import HiveExecutor
BASE_DIR = Path(__file__).resolve().parent
mcp_path = BASE_DIR / "MCP"
sys.path.insert(0, str(mcp_path))

try:
    from hive_executor import HiveExecutor
except ImportError as e:
    print(f"Error: Could not import HiveExecutor from MCP/hive_executor.py")
    print(f"Detail: {e}")
    print("\nPlease run this script using the virtual environment python:")
    print("  .venv/bin/python inspect_impala_tables.py")
    sys.exit(1)

def format_row(row_dict, columns, col_widths):
    formatted_cols = []
    for col, width in zip(columns, col_widths):
        val = row_dict.get(col)
        val_str = str(val) if val is not None else "NULL"
        if len(val_str) > width:
            val_str = val_str[:width-3] + "..."
        formatted_cols.append(val_str.ljust(width))
    return " | ".join(formatted_cols)

def main():
    tables_dir = BASE_DIR / "schema" / "curated_datamodels" / "tables"
    config_path = mcp_path / "hive_config.yaml"

    sql_file = BASE_DIR / "Citizen360_latest_DDLs 1.sql"
    if not sql_file.exists():
        sql_files = list(BASE_DIR.glob("*.sql"))
        if sql_files:
            sql_file = sql_files[0]

    if sql_file.exists():
        print(f"Reading table definitions from SQL file: {sql_file.name}")
        defined_tables = get_sql_tables(str(sql_file))
    else:
        if not tables_dir.exists():
            print(f"Error: Tables schema directory not found at: {tables_dir}")
            sys.exit(1)
        defined_tables = get_yaml_tables(str(tables_dir))

    if not defined_tables:
        print("No tables found to inspect.")
        sys.exit(0)

    # Open the text file for writing
    output_path = BASE_DIR / "impala_tables_sample.txt"
    try:
        out_f = open(output_path, "w", encoding="utf-8")
    except Exception as e:
        print(f"Error opening output file: {e}")
        sys.exit(1)

    def log(msg=""):
        out_f.write(msg + "\n")

    log("=" * 80)
    log("🔍 IMPALA DATABASE INSPECTOR (SQL & SCHEMA TABLES)")
    log(f"Config: {config_path}")
    if sql_file.exists():
        log(f"Source DDL File: {sql_file.name}")
    else:
        log(f"Schemas Folder: {tables_dir}")
    log("=" * 80)
    log()
    log(f"Found {len(defined_tables)} tables defined to inspect.\n")

    print(f"Connecting to Impala (requires valid Kerberos ticket)...")
    os.environ["HIVE_MCP_ENABLED"] = "true"

    try:
        executor = HiveExecutor(str(config_path))
        # Ensure session-scoped settings are optimized for memory footprint
        executor._session_settings = [
            "SET MEM_LIMIT=5g",
            "SET DISABLE_CODEGEN=true",
            "SET NUM_NODES=1",
            "SET MT_DOP=1"
        ]
        print("✓ Connected to Impala. Fetching table data...")

        # Proactively list all tables on the remote database to identify schema mismatches
        try:
            conn = executor._get_connection()
            cursor = conn.cursor()

            cursor.execute("SHOW TABLES IN ap_citizen360")
            citizen_tables = sorted([row[0].lower() for row in cursor.fetchall()])
            log("=" * 80)
            log("📋 EXISTING TABLES IN DATABASE: ap_citizen360")
            log("-" * 80)
            for t in citizen_tables:
                log(f"  - {t}")


            cursor.close()
            print("✓ Successfully listed remote tables in the output log.")
        except Exception as list_err:
            print(f"Warning: Could not list remote tables: {list_err}")
    except Exception as e:
        print(f"Failed to connect to Impala: {e}")
        print("Please ensure you have a valid Kerberos ticket (run kinit).")
        out_f.close()
        sys.exit(1)

    for idx, (db, table) in enumerate(defined_tables, 1):
        print(f"[{idx}/{len(defined_tables)}] Fetching {db}.{table}...")
        log("-" * 80)
        log(f"Table: {db}.{table}")
        log("-" * 80)

        query = f"SELECT * FROM {db}.{table} LIMIT 2;"
        try:
            res = executor.execute(query)
            payload = json.loads(res)
            
            if payload.get("status") == "success":
                columns = payload.get("columns", [])
                rows = payload.get("rows", [])
                
                if not columns:
                    log("  (No columns returned for this table.)")
                    log()
                    continue

                if not rows:
                    log("  (No rows found in this table.)")
                    log(f"  Columns: {', '.join(columns)}")
                    log()
                    continue

                # Calculate column widths dynamically
                col_widths = []
                for col in columns:
                    max_len = len(col)
                    for row in rows:
                        val_str = str(row.get(col)) if row.get(col) is not None else "NULL"
                        max_len = max(max_len, len(val_str))
                    # Bound between 6 and 40 for display
                    width = min(max(max_len, 6), 40)
                    col_widths.append(width)

                # Print Headers
                header_str = " | ".join(col.upper().ljust(w) for col, w in zip(columns, col_widths))
                log(header_str)
                
                # Print Divider
                divider_str = "-+-".join("-" * w for w in col_widths)
                log(divider_str)

                # Print Rows
                for row in rows:
                    log(format_row(row, columns, col_widths))
                
                log(f"\nSuccessfully fetched {len(rows)} records.")
            else:
                log(f"Error querying table: {payload.get('error_msg')}")
        except Exception as e:
            log(f"Error reading table '{table}': {e}")
        log()

    executor.close()
    log("=" * 80)
    log("Done.")
    log("=" * 80)
    
    out_f.close()
    print(f"\n✓ Successfully exported Impala table samples to: {output_path}")

def get_sql_tables(sql_file_path):
    tables = []
    if not os.path.isfile(sql_file_path):
        return tables
    try:
        with open(sql_file_path, "r", encoding="utf-8") as f:
            content = f.read()
        # Strip block comments
        content = re.sub(r"/\*.*?\*/", "", content, flags=re.DOTALL)
        # Strip line comments
        content = re.sub(r"--.*$", "", content, flags=re.MULTILINE)
        
        pattern = r"CREATE\s+(?:EXTERNAL\s+)?TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(?:`?([a-zA-Z0-9_]+)`?\.)?`?([a-zA-Z0-9_]+)`?"
        matches = re.findall(pattern, content, re.IGNORECASE)
        for db, tbl in matches:
            db_name = db if db else "ap_citizen360"
            tables.append((db_name.lower(), tbl.lower()))
    except Exception as e:
        print(f"Error reading SQL file {sql_file_path}: {e}")
    return sorted(list(set(tables)), key=lambda x: (x[0], x[1]))


def get_yaml_tables(tables_dir):
    yaml_tables = []
    if not os.path.isdir(tables_dir):
        return yaml_tables
        
    for root, _, files in os.walk(tables_dir):
        for file in files:
            if file.endswith('.yaml'):
                file_path = os.path.join(root, file)
                try:
                    db_name = "curated_datamodels"
                    table_name = None
                    with open(file_path, 'r', encoding='utf-8') as f:
                        for line in f:
                            stripped = line.strip()
                            if stripped.startswith('database:'):
                                db_name = stripped.split('database:')[1].strip().strip('\'"')
                            elif stripped.startswith('table:'):
                                table_name = stripped.split('table:')[1].strip().strip('\'"')
                    if table_name:
                        yaml_tables.append((db_name, table_name))
                except Exception:
                    pass
    return sorted(list(set(yaml_tables)), key=lambda x: (x[0], x[1]))

if __name__ == '__main__':
    main()
