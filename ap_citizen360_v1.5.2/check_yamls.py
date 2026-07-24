import os
import glob
import yaml
import re

txt_path = '/Users/prakhar/Downloads/Student_Dropout_v1.3.1/impala_tables_samples_output.txt'
distinct_path = '/Users/prakhar/Downloads/Student_Dropout_v1.3.1/impala_distinct_values_output.txt'

tables_in_txt = {}
current_table = None

with open(txt_path, 'r') as f:
    lines = f.readlines()

i = 0
while i < len(lines):
    line = lines[i].strip()
    if line.startswith('Table: curated_datamodels.'):
        current_table = line.split('.')[1]
        tables_in_txt[current_table] = []
        i += 2  # skip the '---' line
        
        if i < len(lines):
            next_line = lines[i].strip()
            if next_line == '(No rows found in this table.)':
                i += 1
                col_line = lines[i].strip()
                if col_line.startswith('Columns:'):
                    cols = col_line.replace('Columns:', '').strip().split(', ')
                    tables_in_txt[current_table] = [c.strip().lower() for c in cols]
            elif 'error_msg' in next_line.lower() or 'error querying table' in next_line.lower():
                # Error line, but let's see if fallback gives columns
                tables_in_txt[current_table] = [next_line]
            else:
                # Header line separated by '|'
                if '|' in next_line:
                    cols = next_line.split('|')
                    tables_in_txt[current_table] = [c.strip().lower() for c in cols]
    i += 1

print(f"Found {len(tables_in_txt)} tables in impala_tables_samples_output.txt")

# Load categorical data from distinct_path
distinct_data = {}
with open(distinct_path, 'r') as f:
    d_lines = f.readlines()

current_d_table = None
current_col = None
j = 0
while j < len(d_lines):
    line = d_lines[j].strip()
    if line.startswith('Table: curated_datamodels.'):
        current_d_table = line.split('.')[1]
        if current_d_table not in distinct_data:
            distinct_data[current_d_table] = {}
    elif line.startswith('Column:'):
        current_col = line.split('Column:')[1].split('(Top')[0].strip().lower()
        if current_d_table:
            distinct_data[current_d_table][current_col] = []
    elif line.startswith('(') and 'No data or table empty' in line:
        pass # Empty
    elif line.startswith('-') or line.startswith('=') or not line:
        pass
    else:
        pass
        
    if line.startswith('  - '):
        if current_d_table and current_col:
            val = line[4:].split(':')[0].strip()
            # If val is 'NULL', we might not want to treat it as a valid categorical example?
            # Let's keep it to see what happens
            distinct_data[current_d_table][current_col].append(val)
    j += 1


# Read YAMLs
yaml_dir = '/Users/prakhar/Downloads/Student_Dropout_v1.3.1/schema/curated_datamodels/tables'
yaml_files = glob.glob(os.path.join(yaml_dir, '**/*.yaml'), recursive=True)

print(f"Found {len(yaml_files)} yaml files")

tables_in_yaml = set()
for yaml_file in yaml_files:
    with open(yaml_file, 'r') as f:
        try:
            data = yaml.safe_load(f)
        except Exception as e:
            print(f"Error loading {yaml_file}: {e}")
            continue
    
    if not data or 'table' not in data:
        continue
        
    table_name = data['table']
    tables_in_yaml.add(table_name)
    yaml_cols = []
    
    missing_in_yaml = set()
    extra_in_yaml = set()
    
    if 'columns' in data:
        yaml_cols = [c['name'].lower() for c in data['columns']]
        
        # Check categorical values mismatch
        for c in data['columns']:
            c_name = c['name'].lower()
            desc = c.get('description', '')
            
            # Extract [Value Examples: ...]
            m = re.search(r'\[Value Examples:\s*(.*?)\]', desc)
            yaml_examples = set()
            if m:
                examples_str = m.group(1)
                yaml_examples = set(re.findall(r"'(.*?)'", examples_str))
                
            # Compare with distinct_data
            if table_name in distinct_data and c_name in distinct_data[table_name]:
                actual_vals = set(distinct_data[table_name][c_name])
                if actual_vals and yaml_examples:
                    if actual_vals != yaml_examples:
                        print(f"[{table_name}.{c_name}] Categorical values mismatch:")
                        print(f"  In YAML: {yaml_examples}")
                        print(f"  In DB  : {actual_vals}")
        
    if table_name in tables_in_txt:
        txt_cols = tables_in_txt[table_name]
        
        missing_in_yaml = set(txt_cols) - set(yaml_cols)
        extra_in_yaml = set(yaml_cols) - set(txt_cols)
        
        if missing_in_yaml or extra_in_yaml:
            print(f"[{table_name}] Column Mismatches found:")
            if missing_in_yaml:
                print(f"  Missing in YAML (present in TXT): {missing_in_yaml}")
            if extra_in_yaml:
                print(f"  Extra in YAML (not in TXT): {extra_in_yaml}")

missing_yamls = set(tables_in_txt.keys()) - tables_in_yaml
if missing_yamls:
    print(f"\nMissing {len(missing_yamls)} YAML files for these tables in TXT:")
    for m in sorted(missing_yamls):
        print(f"  - {m}")
