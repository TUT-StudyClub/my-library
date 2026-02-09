import sqlite3

from fastapi.testclient import TestClient

from src import main


def test_list_library_returns_series_with_status_200(monkeypatch, tmp_path):
    """ライブラリ一覧APIが 200 で登録済み Series 一覧を返す."""
    db_path = tmp_path / "library.db"
    monkeypatch.setenv("DB_PATH", str(db_path))

    with TestClient(main.app) as client:
        created_a = client.post(
            "/api/series",
            json={"title": "作品A", "author": "著者A", "publisher": "出版社A"},
        )
        created_b = client.post(
            "/api/series",
            json={"title": "作品B", "author": "著者B", "publisher": "出版社B"},
        )

        assert created_a.status_code == 201
        assert created_b.status_code == 201

        response = client.get("/api/library")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 2
    assert [item["title"] for item in payload] == ["作品B", "作品A"]
    assert payload[0]["representative_cover_url"] is None
    assert payload[1]["representative_cover_url"] is None


def test_list_library_filters_by_q_and_returns_all_when_q_is_empty(monkeypatch, tmp_path):
    """ライブラリ一覧APIが q で絞り込み、空文字では全件を返す."""
    db_path = tmp_path / "library.db"
    monkeypatch.setenv("DB_PATH", str(db_path))

    with TestClient(main.app) as client:
        client.post(
            "/api/series",
            json={"title": "作品A-前日譚", "author": "著者A", "publisher": "出版社A"},
        )
        client.post(
            "/api/series",
            json={"title": "作品B", "author": "著者B", "publisher": "出版社B"},
        )
        client.post(
            "/api/series",
            json={"title": "作品C", "author": "著者C", "publisher": "出版社C"},
        )

        response_by_title = client.get("/api/library", params={"q": "前日"})
        response_by_author = client.get("/api/library", params={"q": "著者B"})
        response_all = client.get("/api/library", params={"q": ""})
        response_all_with_spaces = client.get("/api/library", params={"q": "   "})

    assert response_by_title.status_code == 200
    assert response_by_author.status_code == 200
    assert response_all.status_code == 200
    assert response_all_with_spaces.status_code == 200

    payload_by_title = response_by_title.json()
    payload_by_author = response_by_author.json()
    payload_all = response_all.json()
    payload_all_with_spaces = response_all_with_spaces.json()

    assert len(payload_by_title) == 1
    assert payload_by_title[0]["title"] == "作品A-前日譚"

    assert len(payload_by_author) == 1
    assert payload_by_author[0]["title"] == "作品B"

    assert len(payload_all) == 3
    assert len(payload_all_with_spaces) == 3


def test_list_library_selects_representative_cover_by_priority(monkeypatch, tmp_path):
    """ライブラリ一覧APIが優先順位どおりに代表表紙URLを返す."""
    db_path = tmp_path / "library.db"
    monkeypatch.setenv("DB_PATH", str(db_path))

    with TestClient(main.app) as client:
        created_v1_priority = client.post(
            "/api/series",
            json={"title": "1巻優先作品", "author": "著者A", "publisher": "出版社A"},
        )
        created_oldest_fallback = client.post(
            "/api/series",
            json={"title": "最古フォールバック作品", "author": "著者B", "publisher": "出版社B"},
        )
        created_null_cover = client.post(
            "/api/series",
            json={"title": "表紙なし作品", "author": "著者C", "publisher": "出版社C"},
        )

        assert created_v1_priority.status_code == 201
        assert created_oldest_fallback.status_code == 201
        assert created_null_cover.status_code == 201

        v1_priority_id = created_v1_priority.json()["id"]
        oldest_fallback_id = created_oldest_fallback.json()["id"]
        null_cover_id = created_null_cover.json()["id"]

        with sqlite3.connect(db_path) as connection:
            connection.executescript(f"""
                INSERT INTO volume (isbn, series_id, volume_number, cover_url, registered_at)
                VALUES ('9780000001001', {v1_priority_id}, 1, 'https://example.com/v1-priority.jpg', '2026-01-03 00:00:00');
                INSERT INTO volume (isbn, series_id, volume_number, cover_url, registered_at)
                VALUES ('9780000001002', {v1_priority_id}, 2, 'https://example.com/v2-older.jpg', '2026-01-01 00:00:00');

                INSERT INTO volume (isbn, series_id, volume_number, cover_url, registered_at)
                VALUES ('9780000002001', {oldest_fallback_id}, 1, NULL, '2026-01-01 00:00:00');
                INSERT INTO volume (isbn, series_id, volume_number, cover_url, registered_at)
                VALUES ('9780000002002', {oldest_fallback_id}, 2, 'https://example.com/v2-oldest.jpg', '2026-01-02 00:00:00');
                INSERT INTO volume (isbn, series_id, volume_number, cover_url, registered_at)
                VALUES ('9780000002003', {oldest_fallback_id}, 3, 'https://example.com/v3-newer.jpg', '2026-01-03 00:00:00');

                INSERT INTO volume (isbn, series_id, volume_number, cover_url, registered_at)
                VALUES ('9780000003001', {null_cover_id}, 1, NULL, '2026-01-01 00:00:00');
                INSERT INTO volume (isbn, series_id, volume_number, cover_url, registered_at)
                VALUES ('9780000003002', {null_cover_id}, 2, '   ', '2026-01-02 00:00:00');
            """)
            connection.commit()

        response = client.get("/api/library")

    assert response.status_code == 200
    payload = response.json()
    representative_cover_by_title = {
        item["title"]: item["representative_cover_url"] for item in payload
    }

    assert representative_cover_by_title["1巻優先作品"] == "https://example.com/v1-priority.jpg"
    assert (
        representative_cover_by_title["最古フォールバック作品"]
        == "https://example.com/v2-oldest.jpg"
    )
    assert representative_cover_by_title["表紙なし作品"] is None
