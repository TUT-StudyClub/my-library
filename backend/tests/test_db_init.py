import sqlite3

import pytest

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


def test_initialize_database_adds_foreign_key_to_existing_volume_table(monkeypatch, tmp_path):
    """既存 volume テーブルに外部キーが無い場合でも起動時に補正される."""
    db_path = tmp_path / "library.db"
    monkeypatch.setenv("DB_PATH", str(db_path))

    with sqlite3.connect(db_path) as connection:
        connection.executescript("""
            CREATE TABLE series (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                author TEXT,
                publisher TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE volume (
                isbn TEXT PRIMARY KEY,
                series_id INTEGER NOT NULL,
                volume_number INTEGER,
                cover_url TEXT,
                registered_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            INSERT INTO series (title, author, publisher) VALUES ('旧作品', '旧著者', '旧出版社');
            INSERT INTO volume (isbn, series_id, volume_number, cover_url)
            VALUES ('9780000000008', 1, 1, 'https://example.com/old-cover.jpg');
            """)

    initialize_database()

    with connect() as connection:
        foreign_keys = connection.execute("PRAGMA foreign_key_list('volume');").fetchall()
        row_count = connection.execute(
            "SELECT COUNT(*) FROM volume WHERE isbn = '9780000000008';"
        ).fetchone()[0]

        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO volume (isbn, series_id, volume_number, cover_url) VALUES (?, ?, ?, ?);",
                ("9780000000009", 999999, 2, "https://example.com/new-cover.jpg"),
            )

    assert any(
        row[2] == "series" and row[3] == "series_id" and row[4] == "id" for row in foreign_keys
    )
    assert row_count == 1


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


def test_insert_rejects_duplicate_isbn(monkeypatch, tmp_path):
    """同じ ISBN の巻は 2回登録できない."""
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
            ("9780000000001", series_id, 1, "https://example.com/cover-1.jpg"),
        )

        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO volume (isbn, series_id, volume_number, cover_url) VALUES (?, ?, ?, ?);",
                ("9780000000001", series_id, 2, "https://example.com/cover-2.jpg"),
            )


def test_insert_rejects_duplicate_series_metadata(monkeypatch, tmp_path):
    """同一メタデータの Series は 2回登録できない."""
    db_path = tmp_path / "library.db"
    monkeypatch.setenv("DB_PATH", str(db_path))

    initialize_database()

    with connect() as connection:
        connection.execute(
            "INSERT INTO series (title, author, publisher) VALUES (?, ?, ?);",
            ("重複作品", None, None),
        )

        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO series (title, author, publisher) VALUES (?, ?, ?);",
                ("重複作品", "", ""),
            )


def test_initialize_database_merges_duplicate_series_before_unique_index(monkeypatch, tmp_path):
    """重複 series が存在しても初期化時に統合され、volume が寄せ直される."""
    db_path = tmp_path / "library.db"
    monkeypatch.setenv("DB_PATH", str(db_path))

    with sqlite3.connect(db_path) as connection:
        connection.executescript("""
            CREATE TABLE series (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                author TEXT,
                publisher TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE volume (
                isbn TEXT PRIMARY KEY,
                series_id INTEGER NOT NULL,
                volume_number INTEGER,
                cover_url TEXT,
                registered_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY(series_id) REFERENCES series(id) ON DELETE CASCADE
            );

            INSERT INTO series (title, author, publisher) VALUES ('統合作品', '統合著者', '統合出版社');
            INSERT INTO series (title, author, publisher) VALUES ('統合作品', '統合著者', '統合出版社');

            INSERT INTO volume (isbn, series_id, volume_number, cover_url)
            VALUES ('9780000000010', 1, 1, NULL);
            INSERT INTO volume (isbn, series_id, volume_number, cover_url)
            VALUES ('9780000000011', 2, 2, NULL);
            """)

    initialize_database()

    with connect() as connection:
        series_rows = connection.execute(
            """
            SELECT id, title, author, publisher
            FROM series
            WHERE title = ? AND author = ? AND publisher = ?;
            """,
            ("統合作品", "統合著者", "統合出版社"),
        ).fetchall()
        assert len(series_rows) == 1

        canonical_series_id = int(series_rows[0][0])
        volume_series_ids = {int(row[0]) for row in connection.execute("""
                SELECT series_id
                FROM volume
                WHERE isbn IN ('9780000000010', '9780000000011');
                """).fetchall()}
        assert volume_series_ids == {canonical_series_id}

        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO series (title, author, publisher) VALUES (?, ?, ?);",
                ("統合作品", "統合著者", "統合出版社"),
            )


def test_volume_requires_existing_series_via_foreign_key(monkeypatch, tmp_path):
    """Volume の series_id には既存 series.id の外部キー制約がある."""
    db_path = tmp_path / "library.db"
    monkeypatch.setenv("DB_PATH", str(db_path))

    initialize_database()

    with connect() as connection:
        foreign_keys = connection.execute("PRAGMA foreign_key_list('volume');").fetchall()

    assert any(
        row[2] == "series" and row[3] == "series_id" and row[4] == "id" for row in foreign_keys
    )


def test_insert_rejects_volume_with_non_existing_series(monkeypatch, tmp_path):
    """存在しない series_id への Volume 登録は拒否される."""
    db_path = tmp_path / "library.db"
    monkeypatch.setenv("DB_PATH", str(db_path))

    initialize_database()

    with connect() as connection:
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO volume (isbn, series_id, volume_number, cover_url) VALUES (?, ?, ?, ?);",
                ("9780000000009", 999999, 1, "https://example.com/cover-9.jpg"),
            )
