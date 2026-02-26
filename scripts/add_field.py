#!/usr/bin/env python3
"""Add a new column to the `users` table and initialize existing rows.

Usage examples:
  python scripts/add_field.py --db kvr_database.db
  python scripts/add_field.py --name new_field --default 0 --db kvr_database.db

This script is safe against invalid column names and will update existing rows
to the provided default value after adding the column.
"""

import argparse
import os
import re
import sqlite3
import sys


IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def infer_type(value: str):
    try:
        int(value)
        return "INTEGER"
    except Exception:
        pass
    try:
        float(value)
        return "REAL"
    except Exception:
        pass
    return "TEXT"


def format_default_literal(value: str, col_type: str):
    if col_type == "TEXT":
        return "'" + value.replace("'", "''") + "'"
    return value


def parse_typed_value(value: str, col_type: str):
    if col_type == "INTEGER":
        return int(value)
    if col_type == "REAL":
        return float(value)
    return value


def main():
    p = argparse.ArgumentParser(description="Add a column to the users table.")
    p.add_argument("--db", help="Path to sqlite database", default=os.environ.get("DATABASE", "kvr_database.db"))
    p.add_argument("--name", help="Column name to add (identifier)")
    p.add_argument("--default", help="Default value to initialize existing rows with")
    p.add_argument("--type", choices=["INTEGER", "REAL", "TEXT"], help="Optional column type (inferred by default)")
    p.add_argument("--not-null", action="store_true", help="Make column NOT NULL (requires a default)")
    args = p.parse_args()

    db = args.db
    if not os.path.exists(db):
        print(f"Database file not found: {db}")
        sys.exit(2)

    name = args.name or input("New column name: ").strip()
    if not name:
        print("Column name is required.")
        sys.exit(2)
    if not IDENT_RE.match(name):
        print("Invalid column name. Use letters, digits and underscores, not starting with a digit.")
        sys.exit(2)

    default = args.default
    if default is None:
        default = input("Default value for existing users (leave blank for empty string): ")
    # Treat empty input as empty string for TEXT, or as 0 for numeric if inferred later

    col_type = args.type or infer_type(default)
    if default == "" and col_type in ("INTEGER", "REAL"):
        # If user entered empty and we inferred numeric, treat as 0
        default = "0"

    default_literal = format_default_literal(default, col_type)

    not_null = args.not_null
    if not_null and default is None:
        print("Cannot set NOT NULL without a default value.")
        sys.exit(2)

    conn = sqlite3.connect(db)
    try:
        cur = conn.cursor()

        # Ensure users table exists
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
        if cur.fetchone() is None:
            print("No 'users' table found in the database.")
            sys.exit(2)

        # Check if column already exists
        cur.execute("PRAGMA table_info(users)")
        cols = [r[1] for r in cur.fetchall()]
        if name in cols:
            print(f"Column '{name}' already exists in users table.")
            sys.exit(0)

        # Build and run ALTER TABLE
        nullable_sql = "NOT NULL" if not_null else ""
        alter_sql = f"ALTER TABLE users ADD COLUMN {name} {col_type} {nullable_sql} DEFAULT {default_literal}"
        cur.execute(alter_sql)
        conn.commit()

        # Ensure existing rows have the desired value (safest approach)
        typed_val = parse_typed_value(default, col_type)
        cur.execute(f"UPDATE users SET {name} = ? WHERE {name} IS NULL", (typed_val,))
        conn.commit()

        print(f"Added column '{name}' ({col_type}) with default {default!r} to users table.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
