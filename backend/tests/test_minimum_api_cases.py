import sqlite3
from pathlib import Path
from typing import Optional

from fastapi.testclient import TestClient

from src import main


def _set_test_db_path(monkeypatch, tmp_path, filename: str = "library.db") -> Path:
    """テスト用DBパスを環境変数へ設定し、そのパスを返す."""
    db_path = tmp_path / filename
    monkeypatch.setenv("DB_PATH", str(db_path))
    return db_path


def _create_series(
    client: TestClient, title: str, author: Optional[str], publisher: Optional[str]
) -> int:
    """Seriesを作成してIDを返す."""
    response = client.post(
        "/api/series",
        json={"title": title, "author": author, "publisher": publisher},
    )
    assert response.status_code == 201
    return int(response.json()["id"])


def _patch_catalog_metadata(
    monkeypatch, metadata_by_isbn: dict[str, main.CatalogVolumeMetadata]
) -> None:
    """ISBNごとのモック書誌を返すように差し替える."""

    def fetch_catalog_volume(isbn: str) -> main.CatalogVolumeMetadata:
        if isbn in metadata_by_isbn:
            return metadata_by_isbn[isbn]

        return main.CatalogVolumeMetadata(
            title="既定作品",
            author="既定著者",
            publisher="既定出版社",
            volume_number=None,
            cover_url=None,
        )

    monkeypatch.setattr(main, "_fetch_catalog_volume_metadata", fetch_catalog_volume)


def test_health_01_returns_ok_when_database_is_available(monkeypatch, tmp_path):
    """HEALTH-01: DB疎通成功時に200と正常ボディを返す."""
    _set_test_db_path(monkeypatch, tmp_path, filename="health-ok.db")

    with TestClient(main.app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "message": "API is running"}


def test_health_02_returns_503_when_database_check_fails(monkeypatch, tmp_path):
    """HEALTH-02: DB疎通失敗時に503の統一エラーを返す."""
    _set_test_db_path(monkeypatch, tmp_path, filename="health-ng.db")

    def raise_connection_error():
        raise sqlite3.OperationalError("database is unavailable")

    monkeypatch.setattr(main, "check_database_connection", raise_connection_error)

    with TestClient(main.app) as client:
        response = client.get("/health")

    assert response.status_code == 503
    assert response.json() == {
        "error": {
            "code": "SERVICE_UNAVAILABLE",
            "message": "Database connection failed",
            "details": {},
        }
    }


def test_library_01_returns_series_in_desc_order(monkeypatch, tmp_path):
    """LIBRARY-01: 登録済みSeriesが新しい順で返る."""
    _set_test_db_path(monkeypatch, tmp_path, filename="library-order.db")

    with TestClient(main.app) as client:
        _create_series(client, "作品A", "著者A", "出版社A")
        _create_series(client, "作品B", "著者B", "出版社B")

        response = client.get("/api/library")

    assert response.status_code == 200
    payload = response.json()
    assert [item["title"] for item in payload] == ["作品B", "作品A"]


def test_library_02_filters_by_title_or_author(monkeypatch, tmp_path):
    """LIBRARY-02: q指定でtitle/authorの部分一致検索ができる."""
    _set_test_db_path(monkeypatch, tmp_path, filename="library-filter.db")

    with TestClient(main.app) as client:
        _create_series(client, "作品A-前日譚", "著者A", "出版社A")
        _create_series(client, "作品B", "著者B", "出版社B")
        _create_series(client, "作品C", "著者C", "出版社C")

        response_by_title = client.get("/api/library", params={"q": "前日"})
        response_by_author = client.get("/api/library", params={"q": "著者B"})

    assert response_by_title.status_code == 200
    assert response_by_author.status_code == 200
    assert [item["title"] for item in response_by_title.json()] == ["作品A-前日譚"]
    assert [item["title"] for item in response_by_author.json()] == ["作品B"]


def test_library_03_returns_all_when_q_is_empty_or_spaces(monkeypatch, tmp_path):
    """LIBRARY-03: qが空文字・空白のみなら全件を返す."""
    _set_test_db_path(monkeypatch, tmp_path, filename="library-empty-q.db")

    with TestClient(main.app) as client:
        _create_series(client, "作品A", "著者A", "出版社A")
        _create_series(client, "作品B", "著者B", "出版社B")
        _create_series(client, "作品C", "著者C", "出版社C")

        response_empty = client.get("/api/library", params={"q": ""})
        response_spaces = client.get("/api/library", params={"q": "   "})

    assert response_empty.status_code == 200
    assert response_spaces.status_code == 200
    assert len(response_empty.json()) == 3
    assert len(response_spaces.json()) == 3


def test_library_04_selects_representative_cover_by_priority(monkeypatch, tmp_path):
    """LIBRARY-04: 代表表紙URLの優先順位どおりに返す."""
    db_path = _set_test_db_path(monkeypatch, tmp_path, filename="library-cover-priority.db")

    with TestClient(main.app) as client:
        v1_priority_id = _create_series(client, "1巻優先作品", "著者A", "出版社A")
        oldest_fallback_id = _create_series(client, "最古フォールバック作品", "著者B", "出版社B")
        null_cover_id = _create_series(client, "表紙なし作品", "著者C", "出版社C")

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
    representative_cover_by_title = {
        item["title"]: item["representative_cover_url"] for item in response.json()
    }
    assert representative_cover_by_title["1巻優先作品"] == "https://example.com/v1-priority.jpg"
    assert (
        representative_cover_by_title["最古フォールバック作品"]
        == "https://example.com/v2-oldest.jpg"
    )
    assert representative_cover_by_title["表紙なし作品"] is None


def test_series_detail_01_returns_empty_volumes(monkeypatch, tmp_path):
    """SERIES-DETAIL-01: Volume未登録Seriesの詳細でvolumesは空配列になる."""
    _set_test_db_path(monkeypatch, tmp_path, filename="series-empty-volumes.db")

    with TestClient(main.app) as client:
        series_id = _create_series(client, "テスト作品", "テスト著者", "テスト出版社")
        response = client.get(f"/api/series/{series_id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == series_id
    assert payload["title"] == "テスト作品"
    assert payload["author"] == "テスト著者"
    assert payload["publisher"] == "テスト出版社"
    assert payload["volumes"] == []


def test_series_detail_02_returns_sorted_volumes(monkeypatch, tmp_path):
    """SERIES-DETAIL-02: volumesが巻数昇順（null末尾）で返る."""
    _set_test_db_path(monkeypatch, tmp_path, filename="series-sorted-volumes.db")

    _patch_catalog_metadata(
        monkeypatch,
        {
            "9780000000001": main.CatalogVolumeMetadata(
                title="巻あり作品",
                author="巻あり著者",
                publisher="巻あり出版社",
                volume_number=2,
                cover_url="https://example.com/covers/volume-2.jpg",
            ),
            "9780000000002": main.CatalogVolumeMetadata(
                title="巻あり作品",
                author="巻あり著者",
                publisher="巻あり出版社",
                volume_number=1,
                cover_url="https://example.com/covers/volume-1.jpg",
            ),
            "9780000000003": main.CatalogVolumeMetadata(
                title="巻あり作品",
                author="巻あり著者",
                publisher="巻あり出版社",
                volume_number=None,
                cover_url=None,
            ),
        },
    )

    with TestClient(main.app) as client:
        series_id = _create_series(client, "巻あり作品", "巻あり著者", "巻あり出版社")
        assert client.post("/api/volumes", json={"isbn": "9780000000001"}).status_code == 201
        assert client.post("/api/volumes", json={"isbn": "9780000000002"}).status_code == 201
        assert client.post("/api/volumes", json={"isbn": "9780000000003"}).status_code == 201

        response = client.get(f"/api/series/{series_id}")

    assert response.status_code == 200
    payload = response.json()
    assert [item["isbn"] for item in payload["volumes"]] == [
        "9780000000002",
        "9780000000001",
        "9780000000003",
    ]
    assert [item["volume_number"] for item in payload["volumes"]] == [1, 2, None]
    assert all(item["registered_at"].endswith("Z") for item in payload["volumes"])


def test_series_detail_03_returns_not_found_when_series_missing(monkeypatch, tmp_path):
    """SERIES-DETAIL-03: 存在しないSeries指定時に404を返す."""
    _set_test_db_path(monkeypatch, tmp_path, filename="series-not-found.db")

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


def test_register_01_creates_volume_with_normalized_isbn(monkeypatch, tmp_path):
    """REGISTER-01: ISBN正規化を行い、巻登録に成功する."""
    _set_test_db_path(monkeypatch, tmp_path, filename="register-created.db")

    _patch_catalog_metadata(
        monkeypatch,
        {
            "9780000000001": main.CatalogVolumeMetadata(
                title="登録作品",
                author="登録著者",
                publisher="登録出版社",
                volume_number=1,
                cover_url="https://example.com/covers/register-1.jpg",
            )
        },
    )

    with TestClient(main.app) as client:
        response = client.post("/api/volumes", json={"isbn": " ９７８-０００００００００１ "})

    assert response.status_code == 201
    payload = response.json()
    assert payload["series"]["title"] == "登録作品"
    assert payload["volume"]["isbn"] == "9780000000001"
    assert payload["volume"]["registered_at"].endswith("Z")


def test_register_02_returns_conflict_when_isbn_already_exists(monkeypatch, tmp_path):
    """REGISTER-02: 同一ISBNの再登録時に409を返す."""
    _set_test_db_path(monkeypatch, tmp_path, filename="register-conflict.db")

    _patch_catalog_metadata(
        monkeypatch,
        {
            "9780000000002": main.CatalogVolumeMetadata(
                title="重複作品",
                author="重複著者",
                publisher="重複出版社",
                volume_number=1,
                cover_url=None,
            )
        },
    )

    with TestClient(main.app) as client:
        first = client.post("/api/volumes", json={"isbn": "9780000000002"})
        second = client.post("/api/volumes", json={"isbn": "9780000000002"})

    assert first.status_code == 201
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "VOLUME_ALREADY_EXISTS"
    assert second.json()["error"]["message"] == "Volume already exists"


def test_register_03_rejects_invalid_isbn(monkeypatch, tmp_path):
    """REGISTER-03: 正規化後13桁にならないISBNを400で拒否する."""
    _set_test_db_path(monkeypatch, tmp_path, filename="register-invalid-isbn.db")

    with TestClient(main.app) as client:
        response = client.post("/api/volumes", json={"isbn": "978-abc"})

    assert response.status_code == 400
    assert response.json() == {
        "error": {
            "code": "INVALID_ISBN",
            "message": "isbn must be 13 digits",
            "details": {"isbn": "978-abc"},
        }
    }


def test_delete_01_deletes_volume_and_returns_payload(monkeypatch, tmp_path):
    """DELETE-01: 指定巻削除に成功し、削除結果を返す."""
    _set_test_db_path(monkeypatch, tmp_path, filename="delete-volume-ok.db")

    _patch_catalog_metadata(
        monkeypatch,
        {
            "9780000000101": main.CatalogVolumeMetadata(
                title="削除確認作品",
                author="削除確認著者",
                publisher="削除確認出版社",
                volume_number=1,
                cover_url="https://example.com/covers/delete-target.jpg",
            ),
            "9780000000102": main.CatalogVolumeMetadata(
                title="削除確認作品",
                author="削除確認著者",
                publisher="削除確認出版社",
                volume_number=2,
                cover_url="https://example.com/covers/remain.jpg",
            ),
        },
    )

    with TestClient(main.app) as client:
        assert client.post("/api/volumes", json={"isbn": "9780000000101"}).status_code == 201
        created_remain = client.post("/api/volumes", json={"isbn": "9780000000102"})
        assert created_remain.status_code == 201

        series_id = created_remain.json()["series"]["id"]
        response = client.delete("/api/volumes/９７８-０００００００１０１")

    assert response.status_code == 200
    assert response.json() == {
        "deleted": {
            "isbn": "9780000000101",
            "seriesId": series_id,
            "remainingVolumeCount": 1,
        }
    }


def test_delete_02_returns_not_found_when_volume_missing(monkeypatch, tmp_path):
    """DELETE-02: 未登録ISBNの指定巻削除は404を返す."""
    _set_test_db_path(monkeypatch, tmp_path, filename="delete-volume-not-found.db")

    with TestClient(main.app) as client:
        response = client.delete("/api/volumes/9780000000999")

    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "VOLUME_NOT_FOUND",
            "message": "Volume not found",
            "details": {"isbn": "9780000000999"},
        }
    }


def test_delete_03_rejects_invalid_isbn_for_delete_volume(monkeypatch, tmp_path):
    """DELETE-03: 正規化後13桁にならないISBN指定削除を400で拒否する."""
    _set_test_db_path(monkeypatch, tmp_path, filename="delete-volume-invalid-isbn.db")

    with TestClient(main.app) as client:
        response = client.delete("/api/volumes/978-abc")

    assert response.status_code == 400
    assert response.json() == {
        "error": {
            "code": "INVALID_ISBN",
            "message": "isbn must be 13 digits",
            "details": {"isbn": "978-abc"},
        }
    }


def test_delete_04_deletes_series_and_child_volumes(monkeypatch, tmp_path):
    """DELETE-04: 全巻削除でSeriesと配下Volumeが削除される."""
    db_path = _set_test_db_path(monkeypatch, tmp_path, filename="delete-series-ok.db")

    with TestClient(main.app) as client:
        series_id = _create_series(client, "全削除作品", "全削除著者", "全削除出版社")

        with sqlite3.connect(db_path) as connection:
            connection.execute(
                """
                INSERT INTO volume (isbn, series_id, volume_number, cover_url)
                VALUES (?, ?, ?, ?);
                """,
                ("9780000005001", series_id, 1, "https://example.com/covers/delete-all-1.jpg"),
            )
            connection.execute(
                """
                INSERT INTO volume (isbn, series_id, volume_number, cover_url)
                VALUES (?, ?, ?, ?);
                """,
                ("9780000005002", series_id, 2, "https://example.com/covers/delete-all-2.jpg"),
            )
            connection.commit()

        response = client.delete(f"/api/series/{series_id}/volumes")

    assert response.status_code == 200
    assert response.json() == {
        "deleted": {
            "seriesId": series_id,
            "deletedVolumeCount": 2,
        }
    }

    with sqlite3.connect(db_path) as connection:
        series_count = connection.execute(
            "SELECT COUNT(*) FROM series WHERE id = ?;",
            (series_id,),
        ).fetchone()
        volume_count = connection.execute(
            "SELECT COUNT(*) FROM volume WHERE series_id = ?;",
            (series_id,),
        ).fetchone()

    assert series_count == (0,)
    assert volume_count == (0,)


def test_delete_05_returns_not_found_when_series_missing(monkeypatch, tmp_path):
    """DELETE-05: 未登録Seriesの全巻削除は404を返す."""
    _set_test_db_path(monkeypatch, tmp_path, filename="delete-series-not-found.db")

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
