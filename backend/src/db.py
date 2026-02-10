import logging
import sqlite3
from collections.abc import Generator
from pathlib import Path

from src.config import load_settings

logger = logging.getLogger(__name__)


def get_db_path() -> Path:
    """解決済みの SQLite ファイルパスを返す."""
    return load_settings().db_path


def connect() -> sqlite3.Connection:
    """外部キーを有効化した SQLite 接続を作成する."""
    connection = sqlite3.connect(get_db_path(), check_same_thread=False)
    connection.execute("PRAGMA foreign_keys = ON;")
    return connection


def get_db_connection() -> Generator[sqlite3.Connection, None, None]:
    """FastAPI の依存関係で使う DB 接続を提供する."""
    connection = connect()

    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def _has_volume_series_foreign_key(connection: sqlite3.Connection) -> bool:
    """volume.series_id -> series.id の外部キーが定義済みか確認する."""
    foreign_keys = connection.execute("PRAGMA foreign_key_list('volume');").fetchall()
    return any(
        row[2] == "series" and row[3] == "series_id" and row[4] == "id" for row in foreign_keys
    )


def _recreate_volume_with_foreign_key(connection: sqlite3.Connection) -> None:
    """既存 volume テーブルを外部キー付き定義で再作成する."""
    connection.executescript("""
        ALTER TABLE volume RENAME TO volume_without_series_fk;

        CREATE TABLE volume (
            isbn TEXT PRIMARY KEY,
            series_id INTEGER NOT NULL,
            volume_number INTEGER,
            cover_url TEXT,
            registered_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY(series_id) REFERENCES series(id) ON DELETE CASCADE
        );

        INSERT INTO volume (isbn, series_id, volume_number, cover_url, registered_at)
        SELECT isbn, series_id, volume_number, cover_url, registered_at
        FROM volume_without_series_fk;

        DROP TABLE volume_without_series_fk;
        """)


def _merge_duplicate_series_by_metadata(connection: sqlite3.Connection) -> None:
    """同一メタデータの重複 series を1件へ統合し、volume.series_id を寄せる."""
    rows = connection.execute("""
        SELECT id, title, author, publisher
        FROM series
        ORDER BY id ASC;
        """).fetchall()

    canonical_id_by_key: dict[tuple[str, str, str], int] = {}
    merge_pairs: list[tuple[int, int]] = []

    for row in rows:
        series_id = int(row[0])
        title = str(row[1])
        author = str(row[2] or "")
        publisher = str(row[3] or "")
        metadata_key = (title, author, publisher)

        canonical_id = canonical_id_by_key.get(metadata_key)
        if canonical_id is None:
            canonical_id_by_key[metadata_key] = series_id
            continue

        merge_pairs.append((series_id, canonical_id))

    for duplicate_id, canonical_id in merge_pairs:
        connection.execute(
            """
            UPDATE volume
            SET series_id = ?
            WHERE series_id = ?;
            """,
            (canonical_id, duplicate_id),
        )
        connection.execute(
            """
            DELETE FROM series
            WHERE id = ?;
            """,
            (duplicate_id,),
        )

    if len(merge_pairs) > 0:
        logger.warning(
            "seriesメタデータ重複を補正しました。mergedSeriesCount=%s",
            len(merge_pairs),
        )


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
            """)

        if not _has_volume_series_foreign_key(connection):
            _recreate_volume_with_foreign_key(connection)

        _merge_duplicate_series_by_metadata(connection)

        connection.executescript("""
            CREATE INDEX IF NOT EXISTS idx_series_title ON series(title);
            CREATE INDEX IF NOT EXISTS idx_series_author ON series(author);
            CREATE UNIQUE INDEX IF NOT EXISTS idx_series_identity
            ON series(title, COALESCE(author, ''), COALESCE(publisher, ''));
            CREATE UNIQUE INDEX IF NOT EXISTS idx_volume_isbn ON volume(isbn);
            CREATE INDEX IF NOT EXISTS idx_volume_series_id ON volume(series_id);
            """)


def check_database_connection() -> None:
    """軽量クエリで DB 接続性を確認する."""
    with connect() as connection:
        connection.execute("SELECT 1;").fetchone()
