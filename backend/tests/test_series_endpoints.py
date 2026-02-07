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
    assert response.json() == {"detail": "title is required"}
