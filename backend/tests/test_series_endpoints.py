import sqlite3

from fastapi.testclient import TestClient

from src import main


def test_create_series_and_get_series_persists_data(monkeypatch, tmp_path):
    """Series 登録APIで書き込み、取得APIで同データを読み取れる."""
    db_path = tmp_path / "library.db"
    monkeypatch.setenv("DB_PATH", str(db_path))

    with TestClient(main.app) as client:
        create_response = client.post(
            "/api/series",
            json={"title": "テスト作品", "author": "テスト著者", "publisher": "テスト出版社"},
        )

        assert create_response.status_code == 201
        created_series = create_response.json()
        assert created_series["title"] == "テスト作品"
        assert created_series["author"] == "テスト著者"
        assert created_series["publisher"] == "テスト出版社"

        get_response = client.get(f"/api/series/{created_series['id']}")

    assert get_response.status_code == 200
    assert get_response.json() == created_series

    with sqlite3.connect(db_path) as connection:
        row = connection.execute(
            """
            SELECT title, author, publisher
            FROM series
            WHERE id = ?;
            """,
            (created_series["id"],),
        ).fetchone()

    assert row == ("テスト作品", "テスト著者", "テスト出版社")


def test_create_series_rejects_blank_title(monkeypatch, tmp_path):
    """Series 登録APIは空タイトルを拒否する."""
    db_path = tmp_path / "library.db"
    monkeypatch.setenv("DB_PATH", str(db_path))

    with TestClient(main.app) as client:
        response = client.post(
            "/api/series",
            json={"title": "  ", "author": "テスト著者", "publisher": "テスト出版社"},
        )

    assert response.status_code == 400
    assert response.json() == {
        "error": {
            "code": "BAD_REQUEST",
            "message": "title is required",
            "details": {},
        }
    }


def test_create_series_returns_standard_error_on_unexpected_exception(monkeypatch, tmp_path):
    """想定外例外でも統一エラーフォーマットを返す."""
    db_path = tmp_path / "library.db"
    monkeypatch.setenv("DB_PATH", str(db_path))

    def raise_unexpected_error(_connection):
        raise RuntimeError("unexpected failure")

    monkeypatch.setattr(main, "_fetch_series_list", raise_unexpected_error)

    with TestClient(main.app, raise_server_exceptions=False) as client:
        response = client.get("/api/series")

    assert response.status_code == 500
    assert response.json() == {
        "error": {
            "code": "INTERNAL_SERVER_ERROR",
            "message": "想定外のエラーが発生しました。",
            "details": {},
        }
    }


def test_create_series_returns_standard_error_on_validation_error(monkeypatch, tmp_path):
    """バリデーションエラーを統一エラーフォーマットで返す."""
    db_path = tmp_path / "library.db"
    monkeypatch.setenv("DB_PATH", str(db_path))

    with TestClient(main.app) as client:
        response = client.post(
            "/api/series", json={"author": "テスト著者", "publisher": "テスト出版社"}
        )

    assert response.status_code == 422
    payload = response.json()
    assert payload["error"]["code"] == "VALIDATION_ERROR"
    assert payload["error"]["message"] == "リクエストパラメータが不正です。"
    assert isinstance(payload["error"]["details"].get("fieldErrors"), list)
    assert len(payload["error"]["details"]["fieldErrors"]) >= 1


def test_list_series_reads_existing_data_via_api(monkeypatch, tmp_path):
    """DBに登録済みの Series を API 経由で取得できる."""
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

        response = client.get("/api/series")

    assert response.status_code == 200
    listed_series = response.json()
    assert len(listed_series) == 2
    assert [item["title"] for item in listed_series] == ["作品B", "作品A"]
