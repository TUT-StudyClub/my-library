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


def test_list_library_supports_q_parameter(monkeypatch, tmp_path):
    """ライブラリ一覧APIが q パラメータで title/author 検索できる."""
    db_path = tmp_path / "library.db"
    monkeypatch.setenv("DB_PATH", str(db_path))

    with TestClient(main.app) as client:
        client.post(
            "/api/series",
            json={"title": "作品A", "author": "著者A", "publisher": "出版社A"},
        )
        client.post(
            "/api/series",
            json={"title": "作品B", "author": "著者B", "publisher": "出版社B"},
        )

        response = client.get("/api/library", params={"q": "著者B"})

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["title"] == "作品B"


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
