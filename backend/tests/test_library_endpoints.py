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
