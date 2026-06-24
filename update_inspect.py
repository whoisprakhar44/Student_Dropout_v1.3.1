import re

with open("inspect_impala_tables.py", "r") as f:
    content = f.read()

fallback_code = """
                if "minimum memory reservation" in payload.get('error_msg', ''):
                    log(f"  [Fallback] Table too wide for pool limits. Fetching first 10 columns only...")
                    try:
                        conn = executor._get_connection()
                        cursor = conn.cursor()
                        cursor.execute(f"DESCRIBE curated_datamodels.{table}")
                        all_cols = [row[0] for row in cursor.fetchall()]
                        # Take first 10 columns
                        subset_cols = all_cols[:10]
                        fallback_query = f"SELECT {', '.join(subset_cols)} FROM curated_datamodels.{table} LIMIT 5"
                        cursor.execute(fallback_query)
                        
                        columns = subset_cols
                        rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
                        cursor.close()
                        
                        if not rows:
                            log("  (No rows found in this table.)")
                            log()
                            continue
                            
                        # Calculate column widths dynamically
                        col_widths = []
                        for col in columns:
                            max_len = len(col)
                            for row in rows:
                                val_str = str(row.get(col)) if row.get(col) is not None else "NULL"
                                max_len = max(max_len, len(val_str))
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
                        
                        log(f"\\nSuccessfully fetched {len(rows)} records (Subset of {len(columns)} columns).")
                        log()
                        continue
                    except Exception as fallback_e:
                        log(f"  Fallback failed: {fallback_e}")
                log(f"Error querying table: {payload.get('error_msg')}")
"""

new_content = content.replace("log(f\"Error querying table: {payload.get('error_msg')}\")", fallback_code.strip())

with open("inspect_impala_tables.py", "w") as f:
    f.write(new_content)
