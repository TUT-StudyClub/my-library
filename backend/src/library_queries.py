import sqlite3
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class LibrarySeries:
    """ライブラリ一覧向けの Series 取得結果."""

    id: int
    title: str
    author: Optional[str]
    publisher: Optional[str]
    representative_cover_url: Optional[str]


@dataclass(frozen=True)
class SeriesVolume:
    """Series 詳細向けの Volume 取得結果."""

    isbn: str
    volume_number: Optional[int]
    cover_url: Optional[str]
    registered_at: str


@dataclass(frozen=True)
class SeriesDetail:
    """Series 詳細向けの取得結果."""

    id: int
    title: str
    author: Optional[str]
    publisher: Optional[str]
    created_at: str
    volumes: list[SeriesVolume]


def fetch_library_series(
    connection: sqlite3.Connection, search_query: Optional[str] = None
) -> list[LibrarySeries]:
    """Series 一覧を取得する（title/author 検索対応）."""
    normalized_query = (search_query or "").strip()
    like_query = f"%{normalized_query}%"

    rows = connection.execute(
        """
        SELECT
            s.id,
            s.title,
            s.author,
            s.publisher,
            (
                SELECT v.cover_url
                FROM volume v
                WHERE v.series_id = s.id
                  AND v.cover_url IS NOT NULL
                  AND TRIM(v.cover_url) <> ''
                ORDER BY
                    CASE WHEN v.volume_number = 1 THEN 0 ELSE 1 END,
                    v.registered_at ASC,
                    v.isbn ASC
                LIMIT 1
            ) AS representative_cover_url
        FROM series s
        WHERE
            (? = '')
            OR s.title LIKE ?
            OR COALESCE(s.author, '') LIKE ?
        ORDER BY s.created_at DESC, s.id DESC;
        """,
        (normalized_query, like_query, like_query),
    ).fetchall()

    return [
        LibrarySeries(
            id=row[0],
            title=row[1],
            author=row[2],
            publisher=row[3],
            representative_cover_url=row[4],
        )
        for row in rows
    ]


def fetch_series_detail(connection: sqlite3.Connection, series_id: int) -> Optional[SeriesDetail]:
    """Series 詳細（作品情報 + 配下 Volume 一覧）を取得する."""
    series_row = connection.execute(
        """
        SELECT id, title, author, publisher, created_at
        FROM series
        WHERE id = ?;
        """,
        (series_id,),
    ).fetchone()
    if series_row is None:
        return None

    volume_rows = connection.execute(
        """
        SELECT isbn, volume_number, cover_url, registered_at
        FROM volume
        WHERE series_id = ?
        ORDER BY
            CASE WHEN volume_number IS NULL THEN 1 ELSE 0 END,
            volume_number ASC,
            registered_at ASC,
            isbn ASC;
        """,
        (series_id,),
    ).fetchall()

    volumes = [
        SeriesVolume(
            isbn=row[0],
            volume_number=row[1],
            cover_url=row[2],
            registered_at=row[3],
        )
        for row in volume_rows
    ]

    return SeriesDetail(
        id=series_row[0],
        title=series_row[1],
        author=series_row[2],
        publisher=series_row[3],
        created_at=series_row[4],
        volumes=volumes,
    )
