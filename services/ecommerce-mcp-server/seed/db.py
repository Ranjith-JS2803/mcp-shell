import os
import sqlite3
from pathlib import Path

SERVICE_DIR = Path(__file__).resolve().parent
SCHEMA_PATH = SERVICE_DIR / "schema.sql"
DB_PATH = Path(os.environ.get("DB_PATH", SERVICE_DIR / "data" / "mcp_server.db"))

REGIONS = ["North", "South", "East", "West", "Central", "International"]
ORDER_STATUSES = ["pending", "completed", "shipped", "cancelled"]
CATEGORIES = [
    "Electronics", "Home & Kitchen", "Clothing", "Sports & Outdoors",
    "Toys & Games", "Books", "Beauty", "Grocery",
]


def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA_PATH.read_text())
    conn.commit()


def is_seeded(conn: sqlite3.Connection) -> bool:
    row = conn.execute(
        "SELECT COUNT(*) AS n FROM sqlite_master WHERE type='table' AND name='orders'"
    ).fetchone()
    if row["n"] == 0:
        return False
    return conn.execute("SELECT COUNT(*) AS n FROM orders").fetchone()["n"] > 0
