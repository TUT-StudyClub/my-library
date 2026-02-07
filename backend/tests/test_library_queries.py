from src.db import connect, initialize_database
from src.library_queries import fetch_library_series, fetch_series_detail


def test_fetch_library_series_supports_search_and_representative_cover(monkeypatch, tmp_path):
    """Series 一覧取得で検索と代表表紙の選定ロジックを満たす."""
    db_path = tmp_path / "library.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    initialize_database()

    with connect() as connection:
        series_a_id = connection.execute(
            """
            INSERT INTO series (title, author, publisher, created_at)
            VALUES (?, ?, ?, ?);
            """,
            ("A-作品", "A-著者", "A-出版社", "2026-01-01 00:00:00"),
        ).lastrowid
        series_b_id = connection.execute(
            """
            INSERT INTO series (title, author, publisher, created_at)
            VALUES (?, ?, ?, ?);
            """,
            ("B-作品", "B-著者", "B-出版社", "2026-01-02 00:00:00"),
        ).lastrowid

        connection.executescript(f"""
            INSERT INTO volume (isbn, series_id, volume_number, cover_url, registered_at)
            VALUES ('9780000000011', {series_a_id}, 1, 'https://example.com/a-v1.jpg', '2026-01-04 00:00:00');
            INSERT INTO volume (isbn, series_id, volume_number, cover_url, registered_at)
            VALUES ('9780000000012', {series_a_id}, 2, 'https://example.com/a-v2.jpg', '2026-01-03 00:00:00');

            INSERT INTO volume (isbn, series_id, volume_number, cover_url, registered_at)
            VALUES ('9780000000021', {series_b_id}, 1, NULL, '2026-01-01 00:00:00');
            INSERT INTO volume (isbn, series_id, volume_number, cover_url, registered_at)
            VALUES ('9780000000022', {series_b_id}, 2, 'https://example.com/b-v2-old.jpg', '2026-01-02 00:00:00');
            INSERT INTO volume (isbn, series_id, volume_number, cover_url, registered_at)
            VALUES ('9780000000023', {series_b_id}, 3, 'https://example.com/b-v3-new.jpg', '2026-01-03 00:00:00');
            """)

        series_list = fetch_library_series(connection)
        searched_series = fetch_library_series(connection, search_query="B-著者")

    representative_cover_by_id = {item.id: item.representative_cover_url for item in series_list}
    assert representative_cover_by_id[series_a_id] == "https://example.com/a-v1.jpg"
    assert representative_cover_by_id[series_b_id] == "https://example.com/b-v2-old.jpg"

    assert len(searched_series) == 1
    assert searched_series[0].id == series_b_id


def test_fetch_series_detail_returns_series_and_sorted_volumes(monkeypatch, tmp_path):
    """Series 詳細取得で作品情報とソート済み Volume 一覧を返す."""
    db_path = tmp_path / "library.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    initialize_database()

    with connect() as connection:
        series_id = connection.execute(
            """
            INSERT INTO series (title, author, publisher, created_at)
            VALUES (?, ?, ?, ?);
            """,
            ("詳細テスト作品", "詳細テスト著者", "詳細テスト出版社", "2026-01-05 00:00:00"),
        ).lastrowid

        connection.executescript(f"""
            INSERT INTO volume (isbn, series_id, volume_number, cover_url, registered_at)
            VALUES ('9780000000103', {series_id}, 3, 'https://example.com/v3.jpg', '2026-01-03 00:00:00');
            INSERT INTO volume (isbn, series_id, volume_number, cover_url, registered_at)
            VALUES ('9780000000101', {series_id}, 1, 'https://example.com/v1.jpg', '2026-01-01 00:00:00');
            INSERT INTO volume (isbn, series_id, volume_number, cover_url, registered_at)
            VALUES ('9780000000199', {series_id}, NULL, 'https://example.com/v-unknown.jpg', '2026-01-02 00:00:00');
            INSERT INTO volume (isbn, series_id, volume_number, cover_url, registered_at)
            VALUES ('9780000000102', {series_id}, 2, 'https://example.com/v2.jpg', '2026-01-04 00:00:00');
            """)

        detail = fetch_series_detail(connection, series_id)

    assert detail is not None
    assert detail.id == series_id
    assert detail.title == "詳細テスト作品"
    assert [volume.volume_number for volume in detail.volumes] == [1, 2, 3, None]
    assert [volume.isbn for volume in detail.volumes] == [
        "9780000000101",
        "9780000000102",
        "9780000000103",
        "9780000000199",
    ]


def test_fetch_series_detail_returns_none_when_series_is_missing(monkeypatch, tmp_path):
    """Series が存在しない場合は None を返す."""
    db_path = tmp_path / "library.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    initialize_database()

    with connect() as connection:
        detail = fetch_series_detail(connection, 99999)

    assert detail is None
