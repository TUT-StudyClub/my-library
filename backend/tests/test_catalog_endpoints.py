from fastapi.testclient import TestClient

from src import main


def test_search_catalog_returns_candidates_with_status_200(monkeypatch, tmp_path):
    """外部カタログ検索APIが 200 で候補一覧DTOを返す."""
    db_path = tmp_path / "library.db"
    monkeypatch.setenv("DB_PATH", str(db_path))

    called = {}

    def fake_search_catalog_by_keyword(q: str, limit: int) -> list[main.CatalogSearchCandidate]:
        called.update({"q": q, "limit": limit})
        return [
            main.CatalogSearchCandidate(
                title="候補作品A",
                author="候補著者A",
                publisher="候補出版社A",
                isbn="9780000000001",
                volume_number=1,
                cover_url="https://example.com/covers/candidate-a-1.jpg",
            ),
            main.CatalogSearchCandidate(
                title="候補作品B",
                author=None,
                publisher=None,
                isbn=None,
                volume_number=None,
                cover_url=None,
            ),
        ]

    monkeypatch.setattr(main, "_search_catalog_by_keyword", fake_search_catalog_by_keyword)

    with TestClient(main.app) as client:
        response = client.get("/api/catalog/search", params={"q": "候補作品", "limit": 2})

    assert response.status_code == 200
    assert called == {"q": "候補作品", "limit": 2}
    assert response.json() == [
        {
            "title": "候補作品A",
            "author": "候補著者A",
            "publisher": "候補出版社A",
            "isbn": "9780000000001",
            "volume_number": 1,
            "cover_url": "https://example.com/covers/candidate-a-1.jpg",
        },
        {
            "title": "候補作品B",
            "author": None,
            "publisher": None,
            "isbn": None,
            "volume_number": None,
            "cover_url": None,
        },
    ]
