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


def test_lookup_catalog_returns_single_candidate_with_status_200(monkeypatch, tmp_path):
    """識別子検索APIが 200 で候補DTOを1件返す."""
    db_path = tmp_path / "library.db"
    monkeypatch.setenv("DB_PATH", str(db_path))

    called = {}

    def fake_lookup_catalog_by_identifier(isbn: str) -> main.CatalogSearchCandidate:
        called.update({"isbn": isbn})
        return main.CatalogSearchCandidate(
            title="識別子候補作品A",
            author="識別子候補著者A",
            publisher="識別子候補出版社A",
            isbn=isbn,
            volume_number=7,
            cover_url="https://example.com/covers/lookup-a-7.jpg",
        )

    monkeypatch.setattr(main, "_lookup_catalog_by_identifier", fake_lookup_catalog_by_identifier)

    with TestClient(main.app) as client:
        response = client.get(
            "/api/catalog/lookup", params={"isbn": " ９７８-０００００００００１ "}
        )

    assert response.status_code == 200
    assert called == {"isbn": "9780000000001"}
    assert response.json() == {
        "title": "識別子候補作品A",
        "author": "識別子候補著者A",
        "publisher": "識別子候補出版社A",
        "isbn": "9780000000001",
        "volume_number": 7,
        "cover_url": "https://example.com/covers/lookup-a-7.jpg",
    }


def test_search_catalog_passes_candidates_through_common_dto_conversion(monkeypatch, tmp_path):
    """キーワード検索APIが共通DTO変換関数を経由して候補を返す."""
    db_path = tmp_path / "library.db"
    monkeypatch.setenv("DB_PATH", str(db_path))

    called = {"count": 0}

    def fake_search_catalog_by_keyword(q: str, limit: int) -> list[main.CatalogSearchCandidate]:
        return [
            main.CatalogSearchCandidate(
                title="変換前候補",
                author="著者",
                publisher=None,
                isbn="9780000000001",
                volume_number=1,
                cover_url=None,
            )
        ]

    def fake_to_catalog_search_candidate_dto(
        candidate: main.CatalogSearchCandidate,
    ) -> main.CatalogSearchCandidate:
        called["count"] += 1
        return main.CatalogSearchCandidate(
            title=f"DTO-{candidate.title}",
            author=candidate.author,
            publisher=candidate.publisher,
            isbn=candidate.isbn,
            volume_number=candidate.volume_number,
            cover_url=candidate.cover_url,
        )

    monkeypatch.setattr(main, "_search_catalog_by_keyword", fake_search_catalog_by_keyword)
    monkeypatch.setattr(
        main, "_to_catalog_search_candidate_dto", fake_to_catalog_search_candidate_dto
    )

    with TestClient(main.app) as client:
        response = client.get("/api/catalog/search", params={"q": "候補", "limit": 1})

    assert response.status_code == 200
    assert called == {"count": 1}
    assert response.json() == [
        {
            "title": "DTO-変換前候補",
            "author": "著者",
            "publisher": None,
            "isbn": "9780000000001",
            "volume_number": 1,
            "cover_url": None,
        }
    ]


def test_lookup_catalog_passes_candidate_through_common_dto_conversion(monkeypatch, tmp_path):
    """識別子検索APIが共通DTO変換関数を経由して候補を返す."""
    db_path = tmp_path / "library.db"
    monkeypatch.setenv("DB_PATH", str(db_path))

    called = {"count": 0}

    def fake_lookup_catalog_by_identifier(isbn: str) -> main.CatalogSearchCandidate:
        return main.CatalogSearchCandidate(
            title="変換前識別子候補",
            author="著者",
            publisher=None,
            isbn=isbn,
            volume_number=2,
            cover_url=None,
        )

    def fake_to_catalog_search_candidate_dto(
        candidate: main.CatalogSearchCandidate,
    ) -> main.CatalogSearchCandidate:
        called["count"] += 1
        return main.CatalogSearchCandidate(
            title=f"DTO-{candidate.title}",
            author=candidate.author,
            publisher=candidate.publisher,
            isbn=candidate.isbn,
            volume_number=candidate.volume_number,
            cover_url=candidate.cover_url,
        )

    monkeypatch.setattr(main, "_lookup_catalog_by_identifier", fake_lookup_catalog_by_identifier)
    monkeypatch.setattr(
        main, "_to_catalog_search_candidate_dto", fake_to_catalog_search_candidate_dto
    )

    with TestClient(main.app) as client:
        response = client.get("/api/catalog/lookup", params={"isbn": "9780000000001"})

    assert response.status_code == 200
    assert called == {"count": 1}
    assert response.json() == {
        "title": "DTO-変換前識別子候補",
        "author": "著者",
        "publisher": None,
        "isbn": "9780000000001",
        "volume_number": 2,
        "cover_url": None,
    }


def test_lookup_catalog_returns_not_found_when_identifier_has_no_result(monkeypatch, tmp_path):
    """識別子検索APIが候補0件時に404の統一エラーを返す."""
    db_path = tmp_path / "library.db"
    monkeypatch.setenv("DB_PATH", str(db_path))

    monkeypatch.setattr(main, "ndl_lookup_by_identifier", lambda isbn: None)

    with TestClient(main.app) as client:
        response = client.get("/api/catalog/lookup", params={"isbn": "9780000000999"})

    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "CATALOG_ITEM_NOT_FOUND",
            "message": "Catalog item not found",
            "details": {
                "isbn": "9780000000999",
                "upstream": "NDL Search",
                "externalFailure": False,
            },
        }
    }


def test_lookup_catalog_rejects_invalid_isbn(monkeypatch, tmp_path):
    """半角数字13桁にならないISBNを 400 で拒否する."""
    db_path = tmp_path / "library.db"
    monkeypatch.setenv("DB_PATH", str(db_path))

    with TestClient(main.app) as client:
        response = client.get("/api/catalog/lookup", params={"isbn": "978-abc"})

    assert response.status_code == 400
    assert response.json() == {
        "error": {
            "code": "INVALID_ISBN",
            "message": "isbn must be 13 digits",
            "details": {"isbn": "978-abc"},
        }
    }
