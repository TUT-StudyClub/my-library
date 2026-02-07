import sqlite3

from src.db import connect, initialize_database


def test_initialize_database_creates_file_and_tables(monkeypatch, tmp_path):
    """初期化で SQLite ファイルと必須テーブルが作成される."""
    db_path = tmp_path / "library.db"
    monkeypatch.setenv("DB_PATH", str(db_path))

    initialize_database()

    assert db_path.exists()

    with sqlite3.connect(db_path) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name IN ('series', 'volume');"
            ).fetchall()
        }

    assert tables == {"series", "volume"}


def test_connect_enables_foreign_keys(monkeypatch, tmp_path):
    """SQLite 接続で外部キー制約が常に有効化される."""
    db_path = tmp_path / "library.db"
    monkeypatch.setenv("DB_PATH", str(db_path))

    initialize_database()

    with connect() as connection:
        pragma_value = connection.execute("PRAGMA foreign_keys;").fetchone()[0]

    assert pragma_value == 1
