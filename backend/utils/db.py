"""
Database utility functions for RVTools
"""
import sqlite3
import pandas as pd
import os
import glob
from datetime import timedelta

# Data directory path - relative to project root
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(os.path.dirname(_BACKEND_DIR), 'data')

# Cache for Excel data
data_cache = {}


def get_db_connection():
    """Get a database connection with Row factory"""
    conn = sqlite3.connect('rvtools.db')
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initialize SQLite database from Excel files"""
    print("Initializing Database...")
    conn = sqlite3.connect('rvtools.db')
    cursor = conn.cursor()
    
    # Clear existing data but keep custom_notes
    tables = cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT IN ('custom_notes', 'sqlite_sequence');"
    ).fetchall()
    for table in tables:
        cursor.execute(f'DROP TABLE IF EXISTS "{table[0]}"')
    conn.commit()

    excel_files = glob.glob(os.path.join(DATA_DIR, "*.xlsx"))
    
    for file_path in excel_files:
        filename = os.path.basename(file_path)
        source_name = os.path.splitext(filename)[0]
        try:
            xls = pd.ExcelFile(file_path)
            for sheet_name in xls.sheet_names:
                try:
                    df = pd.read_excel(xls, sheet_name)
                    df['Source'] = source_name
                    
                    # Robust type conversion
                    for col in df.columns:
                        if pd.api.types.is_timedelta64_dtype(df[col]):
                            df[col] = df[col].astype(str)
                        elif pd.api.types.is_datetime64_any_dtype(df[col]):
                            df[col] = df[col].dt.strftime('%Y-%m-%d %H:%M:%S')
                        else:
                            df[col] = df[col].apply(
                                lambda x: str(x) if isinstance(x, (timedelta, pd.Timedelta)) else x
                            )

                    # Dynamic Schema Evolution
                    cursor.execute(f'PRAGMA table_info("{sheet_name}")')
                    existing_cols = [row[1] for row in cursor.fetchall()]
                    
                    if existing_cols:
                        for col in df.columns:
                            if col not in existing_cols:
                                print(f"Adding column {col} to {sheet_name}")
                                cursor.execute(f'ALTER TABLE "{sheet_name}" ADD COLUMN "{col}" TEXT')
                        conn.commit()

                    df.to_sql(sheet_name, conn, if_exists='append', index=False)
                except Exception as sheet_err:
                    print(f"Error importing sheet {sheet_name} from {filename}: {sheet_err}")
                
            print(f"Finished processing {filename}")
        except Exception as e:
            print(f"Error opening {filename}: {e}")
            import traceback
            traceback.print_exc()
            
    # Create custom_notes table if not exists
    conn.execute('''
        CREATE TABLE IF NOT EXISTS custom_notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            target_type TEXT NOT NULL,
            target_name TEXT NOT NULL,
            note_content TEXT,
            updated_at TEXT,
            UNIQUE(target_type, target_name)
        )
    ''')
    conn.commit()
    conn.close()
    print("Database Initialized Successfully.")


def load_excel_data(filename, sheet_name):
    """Load data from Excel file with caching"""
    cache_key = f"{filename}_{sheet_name}"
    filepath = os.path.join(DATA_DIR, filename)
    mtime = os.path.getmtime(filepath) if os.path.exists(filepath) else None

    cached = data_cache.get(cache_key)
    if cached and cached.get('mtime') == mtime:
        return cached['df']

    df = pd.read_excel(filepath, sheet_name=sheet_name)
    for col in df.columns:
        if df[col].dtype == 'datetime64[ns]':
            df[col] = df[col].astype(str)

    data_cache[cache_key] = {'mtime': mtime, 'df': df}
    return df


def get_all_sources():
    """Get list of all Excel files in data directory"""
    sources = []
    for f in os.listdir(DATA_DIR):
        if f.endswith('.xlsx'):
            name = os.path.splitext(f)[0]
            sources.append({'filename': f, 'name': name})
    return sources


def get_combined_data(sheet_name):
    """Get combined data from all sources via SQLite (much faster than Excel)"""
    conn = sqlite3.connect('rvtools.db')
    try:
        # Check if table exists first
        cursor = conn.cursor()
        cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{sheet_name}';")
        if not cursor.fetchone():
            return pd.DataFrame()
            
        df = pd.read_sql_query(f'SELECT * FROM "{sheet_name}"', conn)
        return df
    except Exception as e:
        print(f"Error reading from DB ({sheet_name}): {e}")
        return pd.DataFrame()
    finally:
        conn.close()


def clear_cache():
    """Clear the Excel data cache"""
    data_cache.clear()
