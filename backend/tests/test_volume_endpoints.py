import sqlite3

from fastapi.testclient import TestClient

from src import main


def test_create_volume_persists_series_and_volume(monkeypatch, tmp_path):
    """ISBN登録APIが Series/Volume を保存し、DBへ反映される."""
    db_path = tmp_path / "library.db"
    monkeypatch.setenv("DB_PATH", str(db_path))

    def fetch_catalog_volume(_isbn: str) -> main.CatalogVolumeMetadata:
        return main.CatalogVolumeMetadata(
            title="テスト作品",
            author="テスト著者",
            publisher="テスト出版社",
            volume_number=1,
            cover_url="https://example.com/covers/test-1.jpg",
        )

    monkeypatch.setattr(main, "_fetch_catalog_volume_metadata", fetch_catalog_volume)

    with TestClient(main.app) as client:
        response = client.post("/api/volumes", json={"isbn": " ９７８-０００００００００１ "})

    assert response.status_code == 201
    payload = response.json()
    assert payload["series"]["title"] == "テスト作品"
    assert payload["series"]["author"] == "テスト著者"
    assert payload["series"]["publisher"] == "テスト出版社"
    assert payload["volume"]["isbn"] == "9780000000001"
    assert payload["volume"]["volume_number"] == 1
    assert payload["volume"]["cover_url"] == "https://example.com/covers/test-1.jpg"
    assert payload["volume"]["registered_at"].endswith("Z")

    with sqlite3.connect(db_path) as connection:
        row = connection.execute(
            """
            SELECT s.title, s.author, s.publisher, v.isbn, v.volume_number, v.cover_url
            FROM series s
            JOIN volume v ON v.series_id = s.id
            WHERE v.isbn = ?;
            """,
            ("9780000000001",),
        ).fetchone()

    assert row == (
        "テスト作品",
        "テスト著者",
        "テスト出版社",
        "9780000000001",
        1,
        "https://example.com/covers/test-1.jpg",
    )


def test_create_volume_reuses_existing_series_on_same_metadata(monkeypatch, tmp_path):
    """同一Seriesメタデータの巻登録時は既存Seriesを再利用する."""
    db_path = tmp_path / "library.db"
    monkeypatch.setenv("DB_PATH", str(db_path))

    def fetch_catalog_volume(isbn: str) -> main.CatalogVolumeMetadata:
        volume_number = 1 if isbn.endswith("01") else 2
        return main.CatalogVolumeMetadata(
            title="再利用作品",
            author="再利用著者",
            publisher="再利用出版社",
            volume_number=volume_number,
            cover_url=None,
        )

    monkeypatch.setattr(main, "_fetch_catalog_volume_metadata", fetch_catalog_volume)

    with TestClient(main.app) as client:
        first = client.post("/api/volumes", json={"isbn": "9780000000001"})
        second = client.post("/api/volumes", json={"isbn": "9780000000002"})

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["series"]["id"] == second.json()["series"]["id"]

    with sqlite3.connect(db_path) as connection:
        series_count = connection.execute("SELECT COUNT(*) FROM series;").fetchone()
        volume_count = connection.execute("SELECT COUNT(*) FROM volume;").fetchone()

    assert series_count == (1,)
    assert volume_count == (2,)


def test_create_volume_returns_conflict_when_isbn_already_exists(monkeypatch, tmp_path):
    """同一ISBNの再登録時に 409 の統一エラーを返す."""
    db_path = tmp_path / "library.db"
    monkeypatch.setenv("DB_PATH", str(db_path))

    def fetch_catalog_volume(_isbn: str) -> main.CatalogVolumeMetadata:
        return main.CatalogVolumeMetadata(
            title="重複作品",
            author="重複著者",
            publisher="重複出版社",
            volume_number=1,
            cover_url=None,
        )

    monkeypatch.setattr(main, "_fetch_catalog_volume_metadata", fetch_catalog_volume)

    with TestClient(main.app) as client:
        first = client.post("/api/volumes", json={"isbn": "9780000000003"})
        second = client.post("/api/volumes", json={"isbn": "9780000000003"})

    assert first.status_code == 201
    assert second.status_code == 409
    assert second.json() == {
        "error": {
            "code": "VOLUME_ALREADY_EXISTS",
            "message": "Volume already exists",
            "details": {
                "isbn": "9780000000003",
                "seriesId": first.json()["series"]["id"],
            },
        }
    }


def test_create_volume_rejects_invalid_isbn(monkeypatch, tmp_path):
    """半角数字13桁にならないISBNを 400 で拒否する."""
    db_path = tmp_path / "library.db"
    monkeypatch.setenv("DB_PATH", str(db_path))

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
