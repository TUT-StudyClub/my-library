import sqlite3

import pytest
from fastapi.testclient import TestClient

from src import main


@pytest.mark.parametrize(
    ("requested_limit", "expected_upstream_limit"),
    [
        (7, 35),
        (40, 100),
    ],
)
def test_search_catalog_by_keyword_uses_wider_upstream_fetch_limit(
    monkeypatch, requested_limit: int, expected_upstream_limit: int
):
    """検索精度向上のため、上流には広めの件数で問い合わせる."""
    called = {}

    def fake_search_by_keyword(q: str, limit: int, page: int) -> list[main.CatalogSearchCandidate]:
        called.update({"q": q, "limit": limit, "page": page})
        return []

    monkeypatch.setattr(main, "search_by_keyword", fake_search_by_keyword)

    candidates = main._search_catalog_by_keyword("候補", requested_limit)

    assert candidates == []
    assert called == {"q": "候補", "limit": expected_upstream_limit, "page": 1}


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
                owned="unknown",
            ),
            main.CatalogSearchCandidate(
                title="候補作品B",
                author=None,
                publisher=None,
                isbn=None,
                volume_number=None,
                cover_url=None,
                owned="unknown",
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
            "owned": False,
        },
        {
            "title": "候補作品B",
            "author": None,
            "publisher": None,
            "isbn": None,
            "volume_number": None,
            "cover_url": None,
            "owned": "unknown",
        },
    ]


def test_search_catalog_assigns_owned_status_from_registered_isbn(monkeypatch, tmp_path):
    """候補ISBNとDB登録済みISBNを突合し、ownedを付与する."""
    db_path = tmp_path / "library.db"
    monkeypatch.setenv("DB_PATH", str(db_path))

    def fake_search_catalog_by_keyword(q: str, limit: int) -> list[main.CatalogSearchCandidate]:
        assert q == "候補"
        assert limit == 3
        return [
            main.CatalogSearchCandidate(
                title="所持済み候補",
                author=None,
                publisher=None,
                isbn="9780000000001",
                volume_number=1,
                cover_url=None,
                owned="unknown",
            ),
            main.CatalogSearchCandidate(
                title="未所持候補",
                author=None,
                publisher=None,
                isbn="9780000000002",
                volume_number=2,
                cover_url=None,
                owned="unknown",
            ),
            main.CatalogSearchCandidate(
                title="ISBN不明候補",
                author=None,
                publisher=None,
                isbn=None,
                volume_number=None,
                cover_url=None,
                owned="unknown",
            ),
        ]

    monkeypatch.setattr(main, "_search_catalog_by_keyword", fake_search_catalog_by_keyword)

    with TestClient(main.app) as client:
        with sqlite3.connect(db_path) as connection:
            series_cursor = connection.execute(
                """
                INSERT INTO series (title, author, publisher)
                VALUES (?, ?, ?);
                """,
                ("既存シリーズ", None, None),
            )
            series_id = int(series_cursor.lastrowid)
            connection.execute(
                """
                INSERT INTO volume (isbn, series_id, volume_number, cover_url)
                VALUES (?, ?, ?, ?);
                """,
                ("9780000000001", series_id, 1, None),
            )
            connection.commit()

        response = client.get("/api/catalog/search", params={"q": "候補", "limit": 3})

    assert response.status_code == 200
    assert response.json() == [
        {
            "title": "所持済み候補",
            "author": None,
            "publisher": None,
            "isbn": "9780000000001",
            "volume_number": 1,
            "cover_url": None,
            "owned": True,
        },
        {
            "title": "未所持候補",
            "author": None,
            "publisher": None,
            "isbn": "9780000000002",
            "volume_number": 2,
            "cover_url": None,
            "owned": False,
        },
        {
            "title": "ISBN不明候補",
            "author": None,
            "publisher": None,
            "isbn": None,
            "volume_number": None,
            "cover_url": None,
            "owned": "unknown",
        },
    ]


def test_search_catalog_filters_exclusion_terms_and_prioritizes_relevant_titles(
    monkeypatch, tmp_path
):
    """検索結果から除外語候補を落とし、関連度の高いタイトルを先頭に並べる."""
    db_path = tmp_path / "library.db"
    monkeypatch.setenv("DB_PATH", str(db_path))

    def fake_search_catalog_by_keyword(q: str, limit: int) -> list[main.CatalogSearchCandidate]:
        assert q == "鬼滅の刃"
        assert limit == 3
        return [
            main.CatalogSearchCandidate(
                title="鬼滅の刃 特装版",
                author="吾峠呼世晴",
                publisher="集英社",
                isbn="9780000000009",
                volume_number=1,
                cover_url=None,
                owned="unknown",
            ),
            main.CatalogSearchCandidate(
                title="無関係作品",
                author="別作者",
                publisher="別出版社",
                isbn="9780000000008",
                volume_number=1,
                cover_url=None,
                owned="unknown",
            ),
            main.CatalogSearchCandidate(
                title="鬼滅の刃 外伝",
                author="吾峠呼世晴",
                publisher="集英社",
                isbn="9780000000002",
                volume_number=2,
                cover_url="https://example.com/covers/kimetsu-gaiden.jpg",
                owned="unknown",
            ),
            main.CatalogSearchCandidate(
                title="鬼滅の刃",
                author="吾峠呼世晴",
                publisher="集英社",
                isbn="9780000000001",
                volume_number=1,
                cover_url="https://example.com/covers/kimetsu-1.jpg",
                owned="unknown",
            ),
        ]

    monkeypatch.setattr(main, "_search_catalog_by_keyword", fake_search_catalog_by_keyword)

    with TestClient(main.app) as client:
        response = client.get("/api/catalog/search", params={"q": "鬼滅の刃", "limit": 3})

    assert response.status_code == 200
    payload = response.json()
    assert [item["title"] for item in payload] == ["鬼滅の刃", "鬼滅の刃 外伝"]
    assert all("特装版" not in item["title"] for item in payload)


def test_search_catalog_deduplicates_same_isbn_and_keeps_richer_candidate(monkeypatch, tmp_path):
    """同一ISBNが重複した場合、情報量が多い候補を残して1件化する."""
    db_path = tmp_path / "library.db"
    monkeypatch.setenv("DB_PATH", str(db_path))

    def fake_search_catalog_by_keyword(q: str, limit: int) -> list[main.CatalogSearchCandidate]:
        assert q == "呪術廻戦"
        assert limit == 5
        return [
            main.CatalogSearchCandidate(
                title="呪術廻戦",
                author=None,
                publisher=None,
                isbn="9780000000010",
                volume_number=None,
                cover_url=None,
                owned="unknown",
            ),
            main.CatalogSearchCandidate(
                title="呪術廻戦",
                author="芥見下々",
                publisher="集英社",
                isbn="9780000000010",
                volume_number=1,
                cover_url="https://example.com/covers/jujutsu-1.jpg",
                owned="unknown",
            ),
            main.CatalogSearchCandidate(
                title="呪術廻戦 0",
                author="芥見下々",
                publisher="集英社",
                isbn="9780000000011",
                volume_number=0,
                cover_url="https://example.com/covers/jujutsu-0.jpg",
                owned="unknown",
            ),
        ]

    monkeypatch.setattr(main, "_search_catalog_by_keyword", fake_search_catalog_by_keyword)

    with TestClient(main.app) as client:
        response = client.get("/api/catalog/search", params={"q": "呪術廻戦", "limit": 5})

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 2
    assert payload[0]["isbn"] == "9780000000010"
    assert payload[0]["volume_number"] == 1
    assert payload[0]["cover_url"] == "https://example.com/covers/jujutsu-1.jpg"


def test_search_catalog_prioritizes_requested_volume_number(monkeypatch, tmp_path):
    """クエリに巻数指定がある場合は一致巻を優先して返す."""
    db_path = tmp_path / "library.db"
    monkeypatch.setenv("DB_PATH", str(db_path))

    def fake_search_catalog_by_keyword(q: str, limit: int) -> list[main.CatalogSearchCandidate]:
        assert q == "葬送のフリーレン 3巻"
        assert limit == 3
        return [
            main.CatalogSearchCandidate(
                title="葬送のフリーレン",
                author="山田鐘人",
                publisher="小学館",
                isbn="9780000000021",
                volume_number=1,
                cover_url=None,
                owned="unknown",
            ),
            main.CatalogSearchCandidate(
                title="葬送のフリーレン",
                author="山田鐘人",
                publisher="小学館",
                isbn="9780000000023",
                volume_number=3,
                cover_url=None,
                owned="unknown",
            ),
            main.CatalogSearchCandidate(
                title="葬送のフリーレン",
                author="山田鐘人",
                publisher="小学館",
                isbn="9780000000022",
                volume_number=2,
                cover_url=None,
                owned="unknown",
            ),
        ]

    monkeypatch.setattr(main, "_search_catalog_by_keyword", fake_search_catalog_by_keyword)

    with TestClient(main.app) as client:
        response = client.get(
            "/api/catalog/search", params={"q": "葬送のフリーレン 3巻", "limit": 3}
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload[0]["volume_number"] == 3
    assert [item["volume_number"] for item in payload] == [3, 1, 2]


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
            owned="unknown",
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
        "owned": False,
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
                owned="unknown",
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
            owned=candidate.owned,
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
            "owned": False,
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
            owned="unknown",
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
            owned=candidate.owned,
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
        "owned": False,
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


@pytest.mark.parametrize(
    ("scenario", "expected_status", "expected_body"),
    [
        (
            "timeout",
            504,
            {
                "error": {
                    "code": "NDL_API_TIMEOUT",
                    "message": "NDL API request timed out",
                    "details": {
                        "upstream": "NDL Search",
                        "externalFailure": True,
                        "failureType": "timeout",
                        "retryable": True,
                        "timeoutSeconds": 10,
                    },
                }
            },
        ),
        (
            "non_200_response",
            502,
            {
                "error": {
                    "code": "NDL_API_BAD_GATEWAY",
                    "message": "NDL API returned non-200 status",
                    "details": {
                        "upstream": "NDL Search",
                        "externalFailure": True,
                        "failureType": "invalidResponse",
                        "retryable": True,
                        "statusCode": 503,
                    },
                }
            },
        ),
    ],
)
def test_search_catalog_replays_representative_upstream_failure_scenarios(
    monkeypatch, tmp_path, mock_ndl_api, scenario: str, expected_status: int, expected_body: dict
):
    """検索APIの代表的な上流異常系をモックで再現し、応答を固定する."""
    db_path = tmp_path / "library.db"
    monkeypatch.setenv("DB_PATH", str(db_path))

    if scenario == "timeout":
        mock_ndl_api.enqueue_timeout()
        mock_ndl_api.enqueue_timeout()
    else:
        mock_ndl_api.enqueue_response(status_code=503)
        mock_ndl_api.enqueue_response(status_code=503)

    with TestClient(main.app) as client:
        response = client.get("/api/catalog/search", params={"q": "候補", "limit": 1})

    assert response.status_code == expected_status
    assert response.json() == expected_body


def test_search_catalog_converts_unexpected_external_exception_to_bad_gateway(
    monkeypatch, tmp_path
):
    """キーワード検索で想定外の外部例外が発生しても 502 の統一エラーを返す."""
    db_path = tmp_path / "library.db"
    monkeypatch.setenv("DB_PATH", str(db_path))

    def raise_unexpected_error(*_args, **_kwargs):
        raise RuntimeError("unexpected external failure")

    monkeypatch.setattr(main, "search_by_keyword", raise_unexpected_error)

    with TestClient(main.app) as client:
        response = client.get("/api/catalog/search", params={"q": "候補", "limit": 1})

    assert response.status_code == 502
    assert response.json() == {
        "error": {
            "code": "NDL_API_BAD_GATEWAY",
            "message": "Failed to connect NDL API",
            "details": {
                "upstream": "NDL Search",
                "externalFailure": True,
                "failureType": "communication",
                "retryable": False,
            },
        }
    }


def test_lookup_catalog_converts_unexpected_external_exception_to_bad_gateway(
    monkeypatch, tmp_path
):
    """識別子検索で想定外の外部例外が発生しても 502 の統一エラーを返す."""
    db_path = tmp_path / "library.db"
    monkeypatch.setenv("DB_PATH", str(db_path))

    def raise_unexpected_error(*_args, **_kwargs):
        raise RuntimeError("unexpected external failure")

    monkeypatch.setattr(main, "ndl_lookup_by_identifier", raise_unexpected_error)

    with TestClient(main.app) as client:
        response = client.get("/api/catalog/lookup", params={"isbn": "9780000000999"})

    assert response.status_code == 502
    assert response.json() == {
        "error": {
            "code": "NDL_API_BAD_GATEWAY",
            "message": "Failed to connect NDL API",
            "details": {
                "upstream": "NDL Search",
                "externalFailure": True,
                "failureType": "communication",
                "retryable": False,
            },
        }
    }


def test_catalog_search_candidate_schema_documents_field_meanings():
    """CatalogSearchCandidateスキーマに意味と欠損時の説明がある."""
    openapi_schema = main.app.openapi()
    candidate_schema = openapi_schema["components"]["schemas"]["CatalogSearchCandidate"]

    assert set(candidate_schema["required"]) == {"title", "owned"}

    properties = candidate_schema["properties"]
    assert properties["title"]["description"] == "候補タイトル（シリーズ名）。必須で返す。"
    assert properties["author"]["description"] == "著者名。取得できない場合はnull。"
    assert properties["publisher"]["description"] == "出版社名。取得できない場合はnull。"
    assert properties["isbn"]["description"] == "ISBN-13（半角数字13桁）。抽出できない場合はnull。"
    assert properties["volume_number"]["description"] == "巻数。抽出できない場合はnull。"
    assert (
        properties["cover_url"]["description"]
        == "表紙URL。書影情報が無い場合はnull（画像バイナリは返さない）。"
    )
    assert (
        properties["owned"]["description"]
        == "所持判定。DB照合で true/false、ISBN欠損など判定不能時はunknown。"
    )


def test_catalog_search_and_lookup_use_the_same_candidate_dto_schema():
    """search/lookupが同一のCatalogSearchCandidate DTOスキーマを参照する."""
    openapi_schema = main.app.openapi()
    search_response_schema = openapi_schema["paths"]["/api/catalog/search"]["get"]["responses"][
        "200"
    ]["content"]["application/json"]["schema"]
    lookup_response_schema = openapi_schema["paths"]["/api/catalog/lookup"]["get"]["responses"][
        "200"
    ]["content"]["application/json"]["schema"]

    assert search_response_schema["items"]["$ref"] == "#/components/schemas/CatalogSearchCandidate"
    assert lookup_response_schema["$ref"] == "#/components/schemas/CatalogSearchCandidate"
