from types import SimpleNamespace
from typing import Any

import httpx
import pytest

from src import ndl_client


def test_ndl_client_fetches_volume_metadata_from_ndl_api(monkeypatch):
    """クライアント経由でNDL APIにアクセスし、巻メタデータを返す."""
    called = {}
    xml_text = """
    <rss xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcndl="http://ndl.go.jp/dcndl/terms/">
      <channel>
        <item>
          <dc:title>テスト作品 第12巻</dc:title>
          <dc:creator>テスト著者</dc:creator>
          <dc:publisher>テスト出版社</dc:publisher>
          <dc:identifier>9780000000123</dc:identifier>
          <dcndl:volume>第12巻</dcndl:volume>
          <enclosure url="https://example.com/covers/test-12.jpg" />
        </item>
      </channel>
    </rss>
    """.strip()

    def fake_get(url: str, params: dict[str, Any], timeout: float):
        called.update({"url": url, "params": params, "timeout": timeout})
        return SimpleNamespace(status_code=200, text=xml_text)

    monkeypatch.setattr(ndl_client.httpx, "get", fake_get)

    request_policy = ndl_client.NdlRequestPolicy(timeout_seconds=8.0, max_retries=0)
    client = ndl_client.NdlClient(base_url="https://example.com/ndl", request_policy=request_policy)
    metadata = client.fetch_catalog_volume_metadata("9780000000123")

    assert called == {
        "url": "https://example.com/ndl",
        "params": {"isbn": "9780000000123", "cnt": 1},
        "timeout": 8.0,
    }
    assert metadata == ndl_client.CatalogVolumeMetadata(
        title="テスト作品",
        author="テスト著者",
        publisher="テスト出版社",
        volume_number=12,
        cover_url="https://example.com/covers/test-12.jpg",
    )


def test_ndl_client_fetches_cover_url_from_thumbnail_link_when_enclosure_is_missing(monkeypatch):
    """Enclosure が無くても書影相当 link から表紙URLを抽出できる."""
    xml_text = """
    <rss xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcndl="http://ndl.go.jp/dcndl/terms/">
      <channel>
        <item>
          <dc:title>サムネイル作品 第7巻</dc:title>
          <dc:creator>サムネイル著者</dc:creator>
          <dc:publisher>サムネイル出版社</dc:publisher>
          <dc:identifier>9780000000123</dc:identifier>
          <dcndl:volume>第7巻</dcndl:volume>
          <link rel="http://ndl.go.jp/dcndl/terms/thumbnail" href="https://example.com/covers/thumb-7.jpg" />
        </item>
      </channel>
    </rss>
    """.strip()

    def fake_get(url: str, params: dict[str, Any], timeout: float):
        return SimpleNamespace(status_code=200, text=xml_text)

    monkeypatch.setattr(ndl_client.httpx, "get", fake_get)
    client = ndl_client.NdlClient(base_url="https://example.com/ndl")

    metadata = client.fetch_catalog_volume_metadata("9780000000123")

    assert metadata.cover_url == "https://example.com/covers/thumb-7.jpg"


def test_ndl_client_returns_none_cover_url_when_only_non_cover_link_exists(monkeypatch):
    """書影相当ではない link のみの場合は cover_url を欠損にする."""
    xml_text = """
    <rss xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcndl="http://ndl.go.jp/dcndl/terms/">
      <channel>
        <item>
          <dc:title>リンクのみ作品 第2巻</dc:title>
          <dc:identifier>9780000000123</dc:identifier>
          <dcndl:volume>第2巻</dcndl:volume>
          <link rel="alternate" href="https://example.com/books/volume-2" />
        </item>
      </channel>
    </rss>
    """.strip()

    def fake_get(url: str, params: dict[str, Any], timeout: float):
        return SimpleNamespace(status_code=200, text=xml_text)

    monkeypatch.setattr(ndl_client.httpx, "get", fake_get)
    client = ndl_client.NdlClient(base_url="https://example.com/ndl")

    metadata = client.fetch_catalog_volume_metadata("9780000000123")

    assert metadata.cover_url is None


def test_ndl_client_returns_timeout_client_error(monkeypatch):
    """NDL APIタイムアウト時に方針回数まで再試行し、504を返す."""
    called_count = 0

    def fake_get(url: str, params: dict[str, Any], timeout: float):
        nonlocal called_count
        called_count += 1
        raise httpx.TimeoutException("timeout")

    monkeypatch.setattr(ndl_client.httpx, "get", fake_get)
    request_policy = ndl_client.NdlRequestPolicy(timeout_seconds=10.0, max_retries=2)
    client = ndl_client.NdlClient(base_url="https://example.com/ndl", request_policy=request_policy)

    with pytest.raises(ndl_client.NdlClientError) as error_info:
        client.fetch_catalog_volume_metadata("9780000000123")

    assert called_count == 3
    assert error_info.value.status_code == 504
    assert error_info.value.to_http_exception_detail() == {
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


def test_ndl_client_retries_retryable_status_and_succeeds(monkeypatch):
    """再試行対象ステータスは方針回数内でリトライして成功できる."""
    called_count = 0
    xml_text = """
    <rss xmlns:dc="http://purl.org/dc/elements/1.1/">
      <channel>
        <item>
          <dc:title>リトライ作品 第1巻</dc:title>
          <dc:identifier>9780000000123</dc:identifier>
        </item>
      </channel>
    </rss>
    """.strip()

    def fake_get(url: str, params: dict[str, Any], timeout: float):
        nonlocal called_count
        called_count += 1
        if called_count == 1:
            return SimpleNamespace(status_code=503, text="")

        return SimpleNamespace(status_code=200, text=xml_text)

    monkeypatch.setattr(ndl_client.httpx, "get", fake_get)
    request_policy = ndl_client.NdlRequestPolicy(timeout_seconds=10.0, max_retries=1)
    client = ndl_client.NdlClient(base_url="https://example.com/ndl", request_policy=request_policy)

    metadata = client.fetch_catalog_volume_metadata("9780000000123")

    assert called_count == 2
    assert metadata == ndl_client.CatalogVolumeMetadata(
        title="リトライ作品",
        author=None,
        publisher=None,
        volume_number=1,
        cover_url=None,
    )


def test_ndl_client_fetches_metadata_from_exact_isbn_item(monkeypatch):
    """巻メタデータ取得は先頭ではなく一致ISBNの item を採用する."""
    xml_text = """
    <rss xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcndl="http://ndl.go.jp/dcndl/terms/">
      <channel>
        <item>
          <dc:title>別作品 第3巻</dc:title>
          <dc:creator>別著者</dc:creator>
          <dc:identifier>9780000000999</dc:identifier>
          <dcndl:volume>第3巻</dcndl:volume>
        </item>
        <item>
          <dc:title>一致作品 第4巻</dc:title>
          <dc:creator>一致著者</dc:creator>
          <dc:publisher>一致出版社</dc:publisher>
          <dc:identifier>9780000000123</dc:identifier>
          <dcndl:volume>第4巻</dcndl:volume>
        </item>
      </channel>
    </rss>
    """.strip()

    def fake_get(url: str, params: dict[str, Any], timeout: float):
        return SimpleNamespace(status_code=200, text=xml_text)

    monkeypatch.setattr(ndl_client.httpx, "get", fake_get)
    client = ndl_client.NdlClient(base_url="https://example.com/ndl")

    metadata = client.fetch_catalog_volume_metadata("9780000000123")

    assert metadata == ndl_client.CatalogVolumeMetadata(
        title="一致作品",
        author="一致著者",
        publisher="一致出版社",
        volume_number=4,
        cover_url=None,
    )


def test_ndl_client_returns_not_found_when_exact_isbn_item_does_not_exist(monkeypatch):
    """一致ISBNの item が無い場合は 404 の統一エラーを返す."""
    xml_text = """
    <rss xmlns:dc="http://purl.org/dc/elements/1.1/">
      <channel>
        <item>
          <dc:title>別作品 第1巻</dc:title>
          <dc:identifier>9780000000999</dc:identifier>
        </item>
      </channel>
    </rss>
    """.strip()

    def fake_get(url: str, params: dict[str, Any], timeout: float):
        return SimpleNamespace(status_code=200, text=xml_text)

    monkeypatch.setattr(ndl_client.httpx, "get", fake_get)
    client = ndl_client.NdlClient(base_url="https://example.com/ndl")

    with pytest.raises(ndl_client.NdlClientError) as error_info:
        client.fetch_catalog_volume_metadata("9780000000123")

    assert error_info.value.status_code == 404
    assert error_info.value.to_http_exception_detail() == {
        "code": "CATALOG_ITEM_NOT_FOUND",
        "message": "Catalog item not found",
        "details": {
            "isbn": "9780000000123",
            "upstream": "NDL Search",
            "externalFailure": False,
        },
    }


def test_ndl_client_returns_not_found_when_item_has_no_isbn(monkeypatch):
    """Item にISBNが無い場合は 404 の統一エラーを返す."""
    xml_text = """
    <rss xmlns:dc="http://purl.org/dc/elements/1.1/">
      <channel>
        <item>
          <dc:title>識別子欠損作品 第1巻</dc:title>
        </item>
      </channel>
    </rss>
    """.strip()

    def fake_get(url: str, params: dict[str, Any], timeout: float):
        return SimpleNamespace(status_code=200, text=xml_text)

    monkeypatch.setattr(ndl_client.httpx, "get", fake_get)
    client = ndl_client.NdlClient(base_url="https://example.com/ndl")

    with pytest.raises(ndl_client.NdlClientError) as error_info:
        client.fetch_catalog_volume_metadata("9780000000123")

    assert error_info.value.status_code == 404
    assert error_info.value.to_http_exception_detail() == {
        "code": "CATALOG_ITEM_NOT_FOUND",
        "message": "Catalog item not found",
        "details": {
            "isbn": "9780000000123",
            "upstream": "NDL Search",
            "externalFailure": False,
        },
    }


def test_ndl_client_converts_communication_error_to_external_failure(monkeypatch):
    """通信失敗を外部失敗の統一エラー情報へ変換する."""
    request = httpx.Request("GET", "https://example.com/ndl")

    def fake_get(url: str, params: dict[str, Any], timeout: float):
        raise httpx.ConnectError("connect failed", request=request)

    monkeypatch.setattr(ndl_client.httpx, "get", fake_get)
    request_policy = ndl_client.NdlRequestPolicy(timeout_seconds=10.0, max_retries=0)
    client = ndl_client.NdlClient(base_url="https://example.com/ndl", request_policy=request_policy)

    with pytest.raises(ndl_client.NdlClientError) as error_info:
        client.fetch_catalog_volume_metadata("9780000000123")

    assert error_info.value.status_code == 502
    assert error_info.value.to_http_exception_detail() == {
        "code": "NDL_API_BAD_GATEWAY",
        "message": "Failed to connect NDL API",
        "details": {
            "upstream": "NDL Search",
            "externalFailure": True,
            "failureType": "communication",
            "retryable": True,
        },
    }


def test_ndl_client_does_not_retry_non_retryable_status(monkeypatch):
    """再試行対象外ステータスは1回で失敗とする."""
    called_count = 0

    def fake_get(url: str, params: dict[str, Any], timeout: float):
        nonlocal called_count
        called_count += 1
        return SimpleNamespace(status_code=400, text="")

    monkeypatch.setattr(ndl_client.httpx, "get", fake_get)
    request_policy = ndl_client.NdlRequestPolicy(timeout_seconds=10.0, max_retries=3)
    client = ndl_client.NdlClient(base_url="https://example.com/ndl", request_policy=request_policy)

    with pytest.raises(ndl_client.NdlClientError) as error_info:
        client.fetch_catalog_volume_metadata("9780000000123")

    assert called_count == 1
    assert error_info.value.status_code == 502
    assert error_info.value.to_http_exception_detail() == {
        "code": "NDL_API_BAD_GATEWAY",
        "message": "NDL API returned non-200 status",
        "details": {
            "upstream": "NDL Search",
            "externalFailure": True,
            "failureType": "invalidResponse",
            "retryable": False,
            "statusCode": 400,
        },
    }


def test_ndl_client_converts_invalid_xml_to_external_failure(monkeypatch):
    """XML不正レスポンスを外部失敗の統一エラー情報へ変換する."""

    def fake_get(url: str, params: dict[str, Any], timeout: float):
        return SimpleNamespace(status_code=200, text="<rss><channel><item></channel></rss>")

    monkeypatch.setattr(ndl_client.httpx, "get", fake_get)
    client = ndl_client.NdlClient(base_url="https://example.com/ndl")

    with pytest.raises(ndl_client.NdlClientError) as error_info:
        client.fetch_catalog_volume_metadata("9780000000123")

    assert error_info.value.status_code == 502
    assert error_info.value.to_http_exception_detail() == {
        "code": "NDL_API_BAD_GATEWAY",
        "message": "NDL API returned invalid XML",
        "details": {
            "upstream": "NDL Search",
            "externalFailure": True,
            "failureType": "invalidResponse",
            "retryable": False,
        },
    }


def test_fetch_catalog_volume_metadata_uses_runtime_settings(monkeypatch):
    """公開入口が設定値の base_url を使ってクライアントを作る."""
    monkeypatch.setattr(
        ndl_client,
        "load_settings",
        lambda: SimpleNamespace(ndl_api_base_url="https://example.com/runtime-ndl"),
    )

    called = {}

    def fake_fetch(self: ndl_client.NdlClient, isbn: str) -> ndl_client.CatalogVolumeMetadata:
        called.update(
            {
                "base_url": self._base_url,
                "request_policy": self._request_policy,
                "isbn": isbn,
            }
        )
        return ndl_client.CatalogVolumeMetadata(
            title="設定確認作品",
            author=None,
            publisher=None,
            volume_number=None,
            cover_url=None,
        )

    monkeypatch.setattr(ndl_client.NdlClient, "fetch_catalog_volume_metadata", fake_fetch)

    metadata = ndl_client.fetch_catalog_volume_metadata("9780000000123")

    assert called == {
        "base_url": "https://example.com/runtime-ndl",
        "request_policy": ndl_client.DEFAULT_REQUEST_POLICY,
        "isbn": "9780000000123",
    }
    assert metadata.title == "設定確認作品"


def test_ndl_client_search_by_keyword_returns_candidates(monkeypatch):
    """キーワード検索で any/cnt/idx を指定し候補一覧を返す."""
    called = {}
    xml_text = """
    <rss xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcndl="http://ndl.go.jp/dcndl/terms/">
      <channel>
        <item>
          <dc:title>検索テスト作品 第3巻</dc:title>
          <dc:creator>検索著者A</dc:creator>
          <dc:publisher>検索出版社A</dc:publisher>
          <dc:identifier>ISBN978-4-000-00000-2</dc:identifier>
          <dcndl:volume>第3巻</dcndl:volume>
          <enclosure url="https://example.com/covers/search-3.jpg" />
        </item>
        <item>
          <title>検索テスト別作品 2巻</title>
          <author>検索著者B</author>
          <dc:identifier>urn:isbn:9784000000005</dc:identifier>
        </item>
      </channel>
    </rss>
    """.strip()

    def fake_get(url: str, params: dict[str, Any], timeout: float):
        called.update({"url": url, "params": params, "timeout": timeout})
        return SimpleNamespace(status_code=200, text=xml_text)

    monkeypatch.setattr(ndl_client.httpx, "get", fake_get)
    request_policy = ndl_client.NdlRequestPolicy(timeout_seconds=7.0, max_retries=0)
    client = ndl_client.NdlClient(base_url="https://example.com/ndl", request_policy=request_policy)

    candidates = client.search_by_keyword("  検索テスト ", limit=2, page=3)

    assert called == {
        "url": "https://example.com/ndl",
        "params": {"any": "検索テスト", "cnt": 2, "idx": 5},
        "timeout": 7.0,
    }
    assert candidates == [
        ndl_client.CatalogSearchCandidate(
            title="検索テスト作品",
            author="検索著者A",
            publisher="検索出版社A",
            isbn="9784000000002",
            volume_number=3,
            cover_url="https://example.com/covers/search-3.jpg",
            owned="unknown",
        ),
        ndl_client.CatalogSearchCandidate(
            title="検索テスト別作品",
            author="検索著者B",
            publisher=None,
            isbn="9784000000005",
            volume_number=2,
            cover_url=None,
            owned="unknown",
        ),
    ]


def test_ndl_client_search_by_keyword_validates_parameters():
    """空キーワードや不正なページング指定は ValueError にする."""
    client = ndl_client.NdlClient(base_url="https://example.com/ndl")

    with pytest.raises(ValueError):
        client.search_by_keyword("   ")

    with pytest.raises(ValueError):
        client.search_by_keyword("検索", limit=0)

    with pytest.raises(ValueError):
        client.search_by_keyword("検索", page=0)


def test_search_by_keyword_uses_runtime_settings(monkeypatch):
    """公開入口が設定値の base_url を使って検索を呼び出す."""
    monkeypatch.setattr(
        ndl_client,
        "load_settings",
        lambda: SimpleNamespace(ndl_api_base_url="https://example.com/runtime-ndl"),
    )

    called = {}

    def fake_search(
        self: ndl_client.NdlClient, q: str, limit: int, page: int
    ) -> list[ndl_client.CatalogSearchCandidate]:
        called.update(
            {
                "base_url": self._base_url,
                "request_policy": self._request_policy,
                "q": q,
                "limit": limit,
                "page": page,
            }
        )
        return [
            ndl_client.CatalogSearchCandidate(
                title="設定確認検索作品",
                author=None,
                publisher=None,
                isbn="9784000000999",
                volume_number=None,
                cover_url=None,
                owned="unknown",
            )
        ]

    monkeypatch.setattr(ndl_client.NdlClient, "search_by_keyword", fake_search)

    candidates = ndl_client.search_by_keyword("テスト", limit=5, page=2)

    assert called == {
        "base_url": "https://example.com/runtime-ndl",
        "request_policy": ndl_client.DEFAULT_REQUEST_POLICY,
        "q": "テスト",
        "limit": 5,
        "page": 2,
    }
    assert candidates[0].title == "設定確認検索作品"


def test_ndl_client_lookup_by_identifier_returns_exact_isbn_candidate(monkeypatch):
    """識別子検索は入力ISBNと一致する候補を優先して1件返す."""
    called = {}
    xml_text = """
    <rss xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcndl="http://ndl.go.jp/dcndl/terms/">
      <channel>
        <item>
          <dc:title>識別子候補作品A 第2巻</dc:title>
          <dc:creator>著者A</dc:creator>
          <dc:identifier>9784000000005</dc:identifier>
        </item>
        <item>
          <dc:title>識別子候補作品B 第1巻</dc:title>
          <dc:creator>著者B</dc:creator>
          <dc:publisher>出版社B</dc:publisher>
          <dc:identifier>urn:isbn:9784000000002</dc:identifier>
          <enclosure url="https://example.com/covers/lookup-b-1.jpg" />
        </item>
      </channel>
    </rss>
    """.strip()

    def fake_get(url: str, params: dict[str, Any], timeout: float):
        called.update({"url": url, "params": params, "timeout": timeout})
        return SimpleNamespace(status_code=200, text=xml_text)

    monkeypatch.setattr(ndl_client.httpx, "get", fake_get)
    request_policy = ndl_client.NdlRequestPolicy(timeout_seconds=6.0, max_retries=0)
    client = ndl_client.NdlClient(base_url="https://example.com/ndl", request_policy=request_policy)

    candidate = client.lookup_by_identifier(" ９７８-４-０００-０００００-２ ")

    assert called == {
        "url": "https://example.com/ndl",
        "params": {"isbn": "9784000000002", "cnt": 10},
        "timeout": 6.0,
    }
    assert candidate == ndl_client.CatalogSearchCandidate(
        title="識別子候補作品B",
        author="著者B",
        publisher="出版社B",
        isbn="9784000000002",
        volume_number=1,
        cover_url="https://example.com/covers/lookup-b-1.jpg",
        owned="unknown",
    )


def test_ndl_client_lookup_by_identifier_returns_first_when_no_exact_match(monkeypatch):
    """一致候補が無い場合は先頭候補を最良候補として返す."""
    xml_text = """
    <rss xmlns:dc="http://purl.org/dc/elements/1.1/">
      <channel>
        <item>
          <dc:title>識別子候補作品C 第4巻</dc:title>
          <dc:identifier>9784000000004</dc:identifier>
        </item>
        <item>
          <dc:title>識別子候補作品D 第5巻</dc:title>
          <dc:identifier>9784000000005</dc:identifier>
        </item>
      </channel>
    </rss>
    """.strip()

    def fake_get(url: str, params: dict[str, Any], timeout: float):
        return SimpleNamespace(status_code=200, text=xml_text)

    monkeypatch.setattr(ndl_client.httpx, "get", fake_get)
    client = ndl_client.NdlClient(base_url="https://example.com/ndl")

    candidate = client.lookup_by_identifier("9784000000999")

    assert candidate == ndl_client.CatalogSearchCandidate(
        title="識別子候補作品C",
        author=None,
        publisher=None,
        isbn="9784000000004",
        volume_number=4,
        cover_url=None,
        owned="unknown",
    )


def test_ndl_client_lookup_by_identifier_returns_none_when_no_candidate(monkeypatch):
    """識別子検索が0件なら None を返す."""
    xml_text = "<rss><channel></channel></rss>"

    def fake_get(url: str, params: dict[str, Any], timeout: float):
        return SimpleNamespace(status_code=200, text=xml_text)

    monkeypatch.setattr(ndl_client.httpx, "get", fake_get)
    client = ndl_client.NdlClient(base_url="https://example.com/ndl")

    candidate = client.lookup_by_identifier("9784000000999")

    assert candidate is None


@pytest.mark.parametrize(
    "raw_isbn",
    [
        "9784000000999",
        " 978-4-000-00099-9 ",
        "９７８-４-０００-０００９９-９",
    ],
)
def test_ndl_client_lookup_by_identifier_normalizes_identifier_like_db(monkeypatch, raw_isbn: str):
    """入力形式が異なってもDB保存形式と同じISBNで検索する."""
    called = {}
    xml_text = "<rss><channel></channel></rss>"

    def fake_get(url: str, params: dict[str, Any], timeout: float):
        called.update({"url": url, "params": params, "timeout": timeout})
        return SimpleNamespace(status_code=200, text=xml_text)

    monkeypatch.setattr(ndl_client.httpx, "get", fake_get)
    client = ndl_client.NdlClient(base_url="https://example.com/ndl")

    candidate = client.lookup_by_identifier(raw_isbn)

    assert candidate is None
    assert called["params"]["isbn"] == "9784000000999"


def test_ndl_client_lookup_by_identifier_validates_parameter():
    """ISBN-13を含まない入力は ValueError にする."""
    client = ndl_client.NdlClient(base_url="https://example.com/ndl")

    with pytest.raises(ValueError):
        client.lookup_by_identifier("識別子なし")

    with pytest.raises(ValueError):
        client.lookup_by_identifier("ISBN978-4-000-00000-2")


def test_lookup_by_identifier_uses_runtime_settings(monkeypatch):
    """公開入口が設定値の base_url を使って識別子検索を呼び出す."""
    monkeypatch.setattr(
        ndl_client,
        "load_settings",
        lambda: SimpleNamespace(ndl_api_base_url="https://example.com/runtime-ndl"),
    )

    called = {}

    def fake_lookup(
        self: ndl_client.NdlClient, isbn: str
    ) -> ndl_client.Optional[ndl_client.CatalogSearchCandidate]:
        called.update(
            {
                "base_url": self._base_url,
                "request_policy": self._request_policy,
                "isbn": isbn,
            }
        )
        return ndl_client.CatalogSearchCandidate(
            title="設定確認識別子作品",
            author=None,
            publisher=None,
            isbn="9784000000999",
            volume_number=None,
            cover_url=None,
            owned="unknown",
        )

    monkeypatch.setattr(ndl_client.NdlClient, "lookup_by_identifier", fake_lookup)

    candidate = ndl_client.lookup_by_identifier("9784000000999")

    assert called == {
        "base_url": "https://example.com/runtime-ndl",
        "request_policy": ndl_client.DEFAULT_REQUEST_POLICY,
        "isbn": "9784000000999",
    }
    assert candidate is not None
    assert candidate.title == "設定確認識別子作品"
