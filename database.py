import sqlite3
from typing import Generator

DATABASE_URL = "clothing_store.db"


def get_db_connection(db_path: str = DATABASE_URL) -> sqlite3.Connection:
    """Creates and configures a SQLite database connection."""
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row  # Allows accessing columns by name
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def get_db() -> Generator[sqlite3.Connection, None, None]:
    """FastAPI dependency that yields a database connection and closes it after the request."""
    conn = get_db_connection()
    try:
        yield conn
    finally:
        conn.close()


def init_db(db_path: str = DATABASE_URL) -> None:
    """Initializes the database schema with products and sales tables."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    # Create products table
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            size TEXT NOT NULL,
            price REAL NOT NULL CHECK(price >= 0),
            cost_price REAL NOT NULL CHECK(cost_price >= 0),
            stock INTEGER NOT NULL CHECK(stock >= 0),
            min_stock_threshold INTEGER NOT NULL DEFAULT 5 CHECK(min_stock_threshold >= 0)
        )
        """
    )

    # Create sales table
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL CHECK(quantity > 0),
            total_revenue REAL NOT NULL,
            total_profit REAL NOT NULL,
            sale_date TEXT NOT NULL,
            FOREIGN KEY (product_id) REFERENCES products (id) ON DELETE CASCADE
        )
        """
    )

    conn.commit()
    conn.close()
