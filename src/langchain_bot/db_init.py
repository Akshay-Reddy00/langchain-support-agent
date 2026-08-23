from pathlib import Path
import sqlite3

PROJECT_ROOT = Path(__file__).resolve().parents[2]

DB_PATH = PROJECT_ROOT / "ecommerce.db"
SQL_SEED_PATH = PROJECT_ROOT / "ecommerce_setup.sql"


def init_database():
    sql_script = SQL_SEED_PATH.read_text(encoding="utf-8")

    with sqlite3.connect(DB_PATH) as conn:
        conn.executescript(sql_script)
        conn.commit()

    return DB_PATH
