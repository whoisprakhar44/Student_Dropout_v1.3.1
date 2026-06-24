#!/usr/bin/env python3
import os
import sys
import json
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

    if not tables_dir.exists():
        print(f"Error: Tables schema directory not found at: {tables_dir}")
        sys.exit(1)

    # Gather table names defined in schema/curated_datamodels/tables
    defined_tables = get_yaml_tables(str(tables_dir))
    if not defined_tables:
        print("No tables found in schemas folder.")
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
    log("🔍 IMPALA DATABASE INSPECTOR (TABLES FOLDER ONLY)")
    log(f"Config: {config_path}")
    log(f"Schemas Folder: {tables_dir}")
    log("=" * 80)
    log()
    log(f"Found {len(defined_tables)} tables defined in the tables folder.\n")

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
    except Exception as e:
        print(f"Failed to connect to Impala: {e}")
        print("Please ensure you have a valid Kerberos ticket (run kinit).")
        out_f.close()
        sys.exit(1)

    for idx, table in enumerate(defined_tables, 1):
        print(f"[{idx}/{len(defined_tables)}] Fetching curated_datamodels.{table}...")
        log("-" * 80)
        log(f"Table: curated_datamodels.{table}")
        log("-" * 80)

        query = f"SELECT * FROM curated_datamodels.{table} LIMIT 5;"
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

def get_yaml_tables(tables_dir):
    yaml_tables = []
    if not os.path.isdir(tables_dir):
        return yaml_tables
        
    for root, _, files in os.walk(tables_dir):
        for file in files:
            if file.endswith('.yaml'):
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        for line in f:
                            if line.strip().startswith('table:'):
                                table_name = line.split('table:')[1].strip().strip('\'"')
                                yaml_tables.append(table_name)
                                break
                except Exception:
                    pass
    return sorted(list(set(yaml_tables)))

if __name__ == '__main__':
    main()
