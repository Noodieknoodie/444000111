import sqlite3
import re
import os
import argparse
from pathlib import Path

def generate_full_schema(cursor, output_file):
    """Generate full SQL schema and write to file without double spacing."""
    cursor.execute("""
        SELECT type, name, sql FROM sqlite_master 
        WHERE name NOT LIKE 'sqlite_%' AND sql IS NOT NULL
        ORDER BY CASE type 
            WHEN 'table' THEN 1 
            WHEN 'view' THEN 2 
            WHEN 'trigger' THEN 3 
            WHEN 'index' THEN 4 
            ELSE 5 
        END, name;
    """)
    
    schema_objects = cursor.fetchall()
    
    with open(output_file, 'w', encoding='utf-8') as f:
        current_type = None
        for obj_type, name, sql in schema_objects:
            if obj_type != current_type:
                if current_type is not None:
                    f.write("\n")
                current_type = obj_type
                f.write(f"-- {obj_type.upper()} DEFINITIONS\n")
            if not sql.strip().endswith(';'):
                sql += ';'
            f.write(f"-- {name}\n")
            f.write(f"{sql}\n")

def generate_compact_schema(conn, output_file):
    """Generate compact schema representation."""
    cursor = conn.cursor()
    output = []
    output.append("[TABLES]")
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
    tables = [row[0] for row in cursor.fetchall()]
    
    for table in tables:
        columns = []
        cursor.execute(f"PRAGMA table_info({table});")
        for _, name, type_, notnull, default_val, pk in cursor.fetchall():
            col_info = name
            if pk:
                col_info += "(pk)"
            if notnull and not pk:
                col_info += "(nn)"
            if default_val is not None:
                col_info += f"(def:{default_val})"
            columns.append({"name": name, "info": col_info})
        
        cursor.execute(f"PRAGMA foreign_key_list({table});")
        for _, _, ref_table, from_col, to_col, on_update, on_delete, _ in cursor.fetchall():
            for col in columns:
                if col["name"] == from_col:
                    cascade = ""
                    if on_delete == "CASCADE":
                        cascade = ",cascade"
                    col["info"] += f"(fk:{ref_table}{cascade})"
                    break
        
        cursor.execute(f"PRAGMA index_list({table});")
        unique_constraints = []
        for _, idx_name, is_unique, _, _ in cursor.fetchall():
            if is_unique:
                cursor.execute(f"PRAGMA index_info({idx_name});")
                unique_cols = [c[2] for c in cursor.fetchall()]
                if len(unique_cols) == 1:
                    for col in columns:
                        if col["name"] == unique_cols[0] and "(unique)" not in col["info"]:
                            col["info"] += "(unique)"
                else:
                    unique_constraints.append(f"UNIQUE({','.join(unique_cols)})")
        
        table_line = f"{table}: {', '.join(col['info'] for col in columns)}"
        if unique_constraints:
            table_line += f" {' '.join(unique_constraints)}"
        output.append(table_line)
    
    output.append("\n[VIEWS]")
    cursor.execute("SELECT name, sql FROM sqlite_master WHERE type='view';")
    for name, sql in cursor.fetchall():
        if not sql:
            continue
        tables_involved = []
        from_match = re.search(r'FROM\s+([a-zA-Z0-9_]+)', sql, re.IGNORECASE)
        if from_match:
            tables_involved.append(from_match.group(1))
        join_matches = re.findall(r'JOIN\s+([a-zA-Z0-9_]+)', sql, re.IGNORECASE)
        tables_involved.extend(join_matches)
        tables_involved = list(dict.fromkeys(tables_involved))
        output.append(f"{name}: {' JOIN '.join(tables_involved)}")
    
    output.append("\n[TRIGGERS]")
    cursor.execute("SELECT name, sql FROM sqlite_master WHERE type='trigger';")
    for name, sql in cursor.fetchall():
        if not sql:
            continue
        timing_match = re.search(r'(BEFORE|AFTER)\s+(INSERT|UPDATE|DELETE)\s+ON\s+([a-zA-Z0-9_]+)', sql, re.IGNORECASE)
        if timing_match:
            timing, event, table = timing_match.groups()
            output.append(f"{name}: {timing} {table} {event}")
    
    output.append("\n[INDEXES]")
    cursor.execute("SELECT tbl_name, sql FROM sqlite_master WHERE type='index' AND name NOT LIKE 'sqlite_%';")
    for table, sql in cursor.fetchall():
        if not sql:
            continue
        columns_match = re.search(r'\(\s*(.*?)\s*\)', sql)
        if columns_match:
            columns_str = columns_match.group(1)
            columns = [col.strip().strip('"').strip('`').strip("'") for col in columns_str.split(',')]
            output.append(f"{table}({', '.join(columns)})")
    
    output.append("\n[RELATIONSHIPS]")
    relationships = {}
    for table in tables:
        cursor.execute(f"PRAGMA foreign_key_list({table});")
        fks = cursor.fetchall()
        if fks:
            relationships[table] = {}
            for _, _, ref_table, from_col, to_col, on_update, on_delete, _ in fks:
                if ref_table not in relationships[table]:
                    relationships[table][ref_table] = []
                relationships[table][ref_table].append(from_col)
    for table, refs in relationships.items():
        targets = []
        for ref_table, cols in refs.items():
            if len(cols) == 1:
                targets.append(f"{ref_table}")
            else:
                targets.append(f"{ref_table}({', '.join(cols)})")
        output.append(f"{table} → {', '.join(targets)}")
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("\n".join(output))

def generate_sample_data(conn, sample_data_file):
    """Generate sample data file with representative rows."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT type, name FROM sqlite_master 
        WHERE type IN ('table', 'view') AND name NOT LIKE 'sqlite_%'
        ORDER BY type, name;
    """)
    objects = cursor.fetchall()
    
    with open(sample_data_file, 'w', encoding='utf-8') as f:
        f.write("----------------\nSAMPLE DATA\n----------------\n")
        for obj_type, name in objects:
            try:
                # Skip views that might be problematic
                if obj_type == 'view' and name in ['DocumentView', 'DocumentProcessingView']:
                    # Use a safer query for these views
                    cursor.execute(f'SELECT * FROM "{name}" LIMIT 1')
                    headers = [desc[0] for desc in cursor.description]
                    
                    f.write(f"-- {obj_type.upper()}: {name}\n")
                    f.write(", ".join(headers) + "\n")
                    
                    cursor.execute(f'SELECT * FROM "{name}" LIMIT 3')
                    rows = cursor.fetchall()
                    for row in rows:
                        row_display = ", ".join('NULL' if v is None else str(v) for v in row)
                        f.write(row_display + "\n")
                    f.write("\n")
                    continue
                
                cursor.execute(f'SELECT COUNT(*) FROM "{name}"')
                count = cursor.fetchone()[0]
                if count == 0:
                    continue
                
                positions = set(range(3)) | \
                            set(range(max(0, count//2 - 1), min(count//2 + 2, count))) | \
                            set(range(max(count - 3, 0), count))
                positions = sorted(positions)
                cursor.execute(f'SELECT * FROM "{name}" LIMIT 1')
                headers = [desc[0] for desc in cursor.description]
                f.write(f"-- {obj_type.upper()}: {name}\n")
                f.write(", ".join(headers) + "\n")
                for pos in positions:
                    cursor.execute(f'SELECT * FROM "{name}" LIMIT 1 OFFSET ?', (pos,))
                    row = cursor.fetchone()
                    if row:
                        row_display = ", ".join('NULL' if v is None else str(v) for v in row)
                        f.write(row_display + "\n")
                f.write("\n")
            except sqlite3.Error as e:
                f.write(f"-- {obj_type.upper()}: {name} - Error: {str(e)}\n\n")
    
    with open(sample_data_file, 'r', encoding='utf-8') as file:
        content = file.read()
    content = re.sub(r'\n\s*\n+', '\n\n', content)
    content = re.sub(r' +\n', '\n', content)
    with open(sample_data_file, 'w', encoding='utf-8') as file:
        file.write(content)

def clean_file_spacing(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        lines = [line.rstrip() for line in file if line.strip()]
    with open(file_path, 'w', encoding='utf-8') as file:
        file.write('\n'.join(lines))

def main():
    parser = argparse.ArgumentParser(description='Generate database schemas and sample data.')
    # Assume project root is the current working directory
    project_root = Path.cwd()
    
    parser.add_argument('--db', dest='database', default=str(project_root / "backend" / "data" / "401k_payments_66.db"),
                        help='Path to SQLite database')
    parser.add_argument('--compact', dest='compact_schema', default=str(project_root / "backend" / "data" / "compact_schema.txt"),
                        help='Output path for compact schema')
    parser.add_argument('--sql', dest='sql_schema', default=str(project_root / "backend" / "data" / "schema.sql"),
                        help='Output path for full SQL schema')
    parser.add_argument('--data', dest='data_file', default=str(project_root / "backend" / "data" / "example_data.txt"),
                        help='Output path for sample data')
    
    args = parser.parse_args()
    
    # Ensure output directories exist
    Path(os.path.dirname(args.compact_schema)).mkdir(parents=True, exist_ok=True)
    Path(os.path.dirname(args.sql_schema)).mkdir(parents=True, exist_ok=True)
    Path(os.path.dirname(args.data_file)).mkdir(parents=True, exist_ok=True)
    
    conn = sqlite3.connect(args.database)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    try:
        generate_compact_schema(conn, args.compact_schema)
        print(f"Compact schema written to {args.compact_schema}")
        
        generate_full_schema(cursor, args.sql_schema)
        print(f"Full SQL schema written to {args.sql_schema}")
        
        generate_sample_data(conn, args.data_file)
        print(f"Sample data written to {args.data_file}")
        
        clean_file_spacing(args.compact_schema)
        clean_file_spacing(args.sql_schema)
        clean_file_spacing(args.data_file)
    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    main()