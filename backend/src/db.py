import os
import sqlite3
from pathlib import Path

from src.config import resolve_db_path


def get_db_path() -> Path:
    """解決済みの SQLite ファイルパスを返す."""
    return resolve_db_path(os.getenv("DB_PATH"))


def connect() -> sqlite3.Connection:
    """外部キーを有効化した SQLite 接続を作成する."""
    connection = sqlite3.connect(get_db_path())
    connection.execute("PRAGMA foreign_keys = ON;")
    return connection


def initialize_database() -> None:
    """DBファイルと最小スキーマを作成する."""
    db_path = get_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)

    with connect() as connection:
        connection.executescript("""
            CREATE TABLE IF NOT EXISTS series (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                author TEXT,
                publisher TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS volume (
                isbn TEXT PRIMARY KEY,
                series_id INTEGER NOT NULL,
                volume_number INTEGER,
                cover_url TEXT,
                registered_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY(series_id) REFERENCES series(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_series_title ON series(title);
            CREATE INDEX IF NOT EXISTS idx_series_author ON series(author);
            CREATE INDEX IF NOT EXISTS idx_volume_series_id ON volume(series_id);
            """)


def check_database_connection() -> None:
    """軽量クエリで DB 接続性を確認する."""
    with connect() as connection:
        connection.execute("SELECT 1;").fetchone()
