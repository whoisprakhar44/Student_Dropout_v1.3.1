#!/usr/bin/env python3
"""
Regenerate the curated SQLite sample database and populate ALL tables with synthetic data.
"""

import sqlite3
import random
import string
import yaml
from pathlib import Path
from create_schema import create_database, find_columns, TABLES_DIR

DB_PATH = Path(__file__).resolve().parent / "database" / "schema.db"

def generate_random_value(col_name, col_data, pools):
    # Map foreign keys to their target primary key pools for solid connections
    pool_mapping = {
        'father_person_id': 'person_id',
        'mother_person_id': 'person_id',
        'husband_person_id': 'person_id',
        'head_person_id': 'person_id',
        'owner_name': 'person_name',
        'reg_no': 'reg_no',
        'ptin': 'ptin',
        'person_name': 'person_name'
    }
    
    pool_name = pool_mapping.get(col_name)
    if not pool_name and (col_name.endswith("_id") or col_name.endswith("_code")):
        pool_name = col_name
        
    if pool_name:
        if pool_name not in pools:
            if pool_name == 'person_name':
                pools[pool_name] = [f"Name_{i:04d}" for i in range(1, 1001)]
            else:
                prefix = pool_name[0].upper()
                pools[pool_name] = [f"{prefix}{i:05d}" for i in range(1, 1001)]
        return random.choice(pools[pool_name])

    # 2. If it has distinct values, pick one (ignoring NULL for synthetic data)
    distinct_vals = col_data.get("distinct")
    if distinct_vals and isinstance(distinct_vals, list):
        valid_vals = [v for v in distinct_vals if str(v).upper() not in ('NULL', 'NONE')]
        if valid_vals:
            return random.choice(valid_vals)

    # 3. Generate based on type
    raw_type = col_data.get("type", "TEXT").upper()
    if "INT" in raw_type or "BIGINT" in raw_type:
        return random.randint(1, 1000)
    elif "FLOAT" in raw_type or "DOUBLE" in raw_type or "DECIMAL" in raw_type or "REAL" in raw_type:
        return round(random.uniform(10.0, 10000.0), 2)
    elif "BOOLEAN" in raw_type:
        return random.choice([0, 1])  # SQLite boolean is 0/1
    elif "DATE" in raw_type or "TIMESTAMP" in raw_type:
        year = random.randint(2000, 2024)
        month = random.randint(1, 12)
        day = random.randint(1, 28)
        return f"{year}-{month:02d}-{day:02d}"
    else:
        # Default TEXT
        return f"Mock_{col_name}_{random.randint(1,100)}"


def generate_synthetic_data() -> None:
    create_database(replace=True)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print("Parsing YAML schemas and generating data for ALL tables...")
    pools = {}
    
    # Ensure person_id pool exists for the 1000 students
    pools['person_id'] = [f"P{i:05d}" for i in range(1, 1001)]
    
    for file_path in sorted(TABLES_DIR.rglob("*.yaml")):
        content = file_path.read_text(encoding="utf-8")
        doc = yaml.safe_load(content)
        if doc and doc.get("table"):
            table = doc["table"]
            
            cols_dict = {}
            for col in find_columns(doc):
                cols_dict[col["name"]] = col
                
            columns = list(cols_dict.keys())
            if not columns:
                continue
                
            placeholders = ", ".join(["?" for _ in columns])
            insert_query = f'INSERT INTO "{table}" ({", ".join([f"{c}" for c in columns])}) VALUES ({placeholders})'
            
            num_rows = 1000 if table in ("dim_person", "dim_student") else 100
            
            for _ in range(num_rows):
                row_values = []
                for col_name in columns:
                    col_data = cols_dict[col_name]
                    val = generate_random_value(col_name, col_data, pools)
                    row_values.append(val)
                    
                try:
                    cursor.execute(insert_query, row_values)
                except sqlite3.Error as e:
                    print(f"Error inserting into {table}: {e}")
                    pass # Ignore unique constraint violations for synthetic data
                    
            print(f"Generated {num_rows} rows for {table}")
            
    conn.commit()
    conn.close()
    print("Mock data inserted successfully for all tables!")

if __name__ == "__main__":
    generate_synthetic_data()
