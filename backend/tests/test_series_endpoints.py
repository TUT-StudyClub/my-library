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
    payload = get_response.json()
    assert payload["id"] == created_series["id"]
    assert payload["title"] == created_series["title"]
    assert payload["author"] == created_series["author"]
    assert payload["publisher"] == created_series["publisher"]
    assert payload["volumes"] == []

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


def test_get_series_returns_series_with_registered_volumes(monkeypatch, tmp_path):
    """Series 取得APIで登録済み Volume 一覧を返す."""
    db_path = tmp_path / "library.db"
    monkeypatch.setenv("DB_PATH", str(db_path))

    def fetch_catalog_volume(isbn: str) -> main.CatalogVolumeMetadata:
        if isbn.endswith("0001"):
            return main.CatalogVolumeMetadata(
                title="巻あり作品",
                author="巻あり著者",
                publisher="巻あり出版社",
                volume_number=2,
                cover_url="https://example.com/covers/volume-2.jpg",
            )

        if isbn.endswith("0002"):
            return main.CatalogVolumeMetadata(
                title="巻あり作品",
                author="巻あり著者",
                publisher="巻あり出版社",
                volume_number=1,
                cover_url="https://example.com/covers/volume-1.jpg",
            )

        return main.CatalogVolumeMetadata(
            title="巻あり作品",
            author="巻あり著者",
            publisher="巻あり出版社",
            volume_number=None,
            cover_url=None,
        )

    monkeypatch.setattr(main, "_fetch_catalog_volume_metadata", fetch_catalog_volume)

    with TestClient(main.app) as client:
        create_response = client.post(
            "/api/series",
            json={"title": "巻あり作品", "author": "巻あり著者", "publisher": "巻あり出版社"},
        )
        assert create_response.status_code == 201
        series_id = create_response.json()["id"]

        response_volume_2 = client.post("/api/volumes", json={"isbn": "9780000000001"})
        response_volume_1 = client.post("/api/volumes", json={"isbn": "9780000000002"})
        response_volume_unknown = client.post("/api/volumes", json={"isbn": "9780000000003"})
        get_response = client.get(f"/api/series/{series_id}")

    assert response_volume_2.status_code == 201
    assert response_volume_1.status_code == 201
    assert response_volume_unknown.status_code == 201
    assert get_response.status_code == 200

    payload = get_response.json()
    assert payload["id"] == series_id
    assert payload["title"] == "巻あり作品"
    assert payload["author"] == "巻あり著者"
    assert payload["publisher"] == "巻あり出版社"
    assert [volume["isbn"] for volume in payload["volumes"]] == [
        "9780000000002",
        "9780000000001",
        "9780000000003",
    ]
    assert [volume["volume_number"] for volume in payload["volumes"]] == [1, 2, None]
    assert [volume["cover_url"] for volume in payload["volumes"]] == [
        "https://example.com/covers/volume-1.jpg",
        "https://example.com/covers/volume-2.jpg",
        None,
    ]
    assert all(volume["registered_at"].endswith("Z") for volume in payload["volumes"])


def test_get_series_returns_not_found_error_when_series_does_not_exist(monkeypatch, tmp_path):
    """存在しない Series ID 指定時に 404 の統一エラーを返す."""
    db_path = tmp_path / "library.db"
    monkeypatch.setenv("DB_PATH", str(db_path))

    with TestClient(main.app) as client:
        response = client.get("/api/series/999999")

    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "SERIES_NOT_FOUND",
            "message": "Series not found",
            "details": {"seriesId": 999999},
        }
    }


def test_delete_series_volumes_removes_series_and_get_returns_404(monkeypatch, tmp_path):
    """全巻削除API実行後、Series取得APIは404を返す."""
    db_path = tmp_path / "library.db"
    monkeypatch.setenv("DB_PATH", str(db_path))

    def fetch_catalog_volume(isbn: str) -> main.CatalogVolumeMetadata:
        if isbn.endswith("0001"):
            return main.CatalogVolumeMetadata(
                title="全削除作品",
                author="全削除著者",
                publisher="全削除出版社",
                volume_number=1,
                cover_url="https://example.com/covers/delete-all-1.jpg",
            )

        return main.CatalogVolumeMetadata(
            title="全削除作品",
            author="全削除著者",
            publisher="全削除出版社",
            volume_number=2,
            cover_url="https://example.com/covers/delete-all-2.jpg",
        )

    monkeypatch.setattr(main, "_fetch_catalog_volume_metadata", fetch_catalog_volume)

    with TestClient(main.app) as client:
        create_response = client.post(
            "/api/series",
            json={"title": "全削除作品", "author": "全削除著者", "publisher": "全削除出版社"},
        )
        assert create_response.status_code == 201
        series_id = create_response.json()["id"]

        first_volume = client.post("/api/volumes", json={"isbn": "9780000000001"})
        second_volume = client.post("/api/volumes", json={"isbn": "9780000000002"})
        assert first_volume.status_code == 201
        assert second_volume.status_code == 201

        delete_response = client.delete(f"/api/series/{series_id}/volumes")
        get_response = client.get(f"/api/series/{series_id}")

    assert delete_response.status_code == 200
    assert delete_response.json() == {
        "deleted": {
            "seriesId": series_id,
            "deletedVolumeCount": 2,
        }
    }

    assert get_response.status_code == 404
    assert get_response.json() == {
        "error": {
            "code": "SERIES_NOT_FOUND",
            "message": "Series not found",
            "details": {"seriesId": series_id},
        }
    }

    with sqlite3.connect(db_path) as connection:
        series_count = connection.execute(
            """
            SELECT COUNT(*)
            FROM series
            WHERE id = ?;
            """,
            (series_id,),
        ).fetchone()
        volume_count = connection.execute(
            """
            SELECT COUNT(*)
            FROM volume
            WHERE series_id = ?;
            """,
            (series_id,),
        ).fetchone()

    assert series_count == (0,)
    assert volume_count == (0,)


def test_delete_series_volumes_returns_not_found_when_series_does_not_exist(monkeypatch, tmp_path):
    """未登録Seriesの全巻削除で 404 の統一エラーを返す."""
    db_path = tmp_path / "library.db"
    monkeypatch.setenv("DB_PATH", str(db_path))

    with TestClient(main.app) as client:
        response = client.delete("/api/series/999999/volumes")

    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "SERIES_NOT_FOUND",
            "message": "Series not found",
            "details": {"seriesId": 999999},
        }
    }


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
