"""
DB migration: add error_code and last_error_detail columns to tubi_jobs and tubi_analyses.
Safe to re-run (ignores duplicate column errors).
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "calligraphy.db")

MIGRATIONS = [
    ("tubi_jobs", "error_code", "VARCHAR(50)"),
    ("tubi_jobs", "last_error_detail", "TEXT"),
    ("tubi_analyses", "error_code", "VARCHAR(50)"),
]

def main():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    for table, column, col_type in MIGRATIONS:
        try:
            cur.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
            print(f"  + {table}.{column}")
        except sqlite3.OperationalError as e:
            if "duplicate column" in str(e).lower():
                print(f"  = {table}.{column} (already exists)")
            else:
                print(f"  ! {table}.{column}: {e}")

    conn.commit()
    conn.close()
    print("Done.")

if __name__ == "__main__":
    main()
