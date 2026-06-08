#!/usr/bin/env python3
"""
Introspect columns of production tables from Impala.
"""

import sys
import yaml
from pathlib import Path

# Paths
ROOT_DIR = Path(__file__).resolve().parent
MCP_DIR = ROOT_DIR / "MCP"

def main():
    config_path = MCP_DIR / "hive_config.yaml"
    if not config_path.is_file():
        print(f"Error: hive_config.yaml not found at {config_path}")
        sys.exit(1)

    with open(config_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    query_engine = cfg.get("query_engine", {})
    host = query_engine.get("host")
    port = int(query_engine.get("port", 21050))
    kerberos_service_name = query_engine.get("kerberos", {}).get("service_name", "impala")

    print(f"Connecting to Impala at {host}:{port} using GSSAPI (service={kerberos_service_name})...")
    try:
        from impala.dbapi import connect
        conn = connect(
            host=host,
            port=port,
            auth_mechanism="GSSAPI",
            kerberos_service_name=kerberos_service_name
        )
    except Exception as e:
        print(f"Error connecting: {e}")
        sys.exit(1)

    cursor = conn.cursor()

    tables = [
        "curated_datamodels.mid_day_meal_serving_fact",
        "curated_datamodels.ration_card_family",
        "curated_datamodels.citizen_family_master",
        "curated_datamodels.citizen_utility_connection"
    ]

    for table in tables:
        print(f"\n--- Columns in {table} ---")
        try:
            cursor.execute(f"SELECT * FROM {table} LIMIT 1")
            description = cursor.description or []
            columns = [col[0] for col in description]
            print(columns)
        except Exception as e:
            print(f"Error: {e}")

    cursor.close()
    conn.close()

if __name__ == "__main__":
    main()
