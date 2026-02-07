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


def test_insert_and_select_minimum_series_and_volume(monkeypatch, tmp_path):
    """Series/Volume の最低限の INSERT/SELECT が通る."""
    db_path = tmp_path / "library.db"
    monkeypatch.setenv("DB_PATH", str(db_path))

    initialize_database()

    with connect() as connection:
        cursor = connection.execute(
            "INSERT INTO series (title, author, publisher) VALUES (?, ?, ?);",
            ("テスト作品", "テスト著者", "テスト出版社"),
        )
        series_id = cursor.lastrowid

        connection.execute(
            "INSERT INTO volume (isbn, series_id, volume_number, cover_url) VALUES (?, ?, ?, ?);",
            ("9780000000001", series_id, 1, "https://example.com/cover.jpg"),
        )

        row = connection.execute(
            """
            SELECT s.title, v.isbn, v.volume_number
            FROM series s
            JOIN volume v ON v.series_id = s.id
            WHERE v.isbn = ?;
            """,
            ("9780000000001",),
        ).fetchone()

    assert row == ("テスト作品", "9780000000001", 1)
