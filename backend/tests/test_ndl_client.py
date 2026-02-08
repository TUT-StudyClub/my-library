from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from fastapi import HTTPException

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


def test_ndl_client_returns_timeout_http_exception(monkeypatch):
    """NDL APIタイムアウト時に方針回数まで再試行し、504を返す."""
    called_count = 0

    def fake_get(url: str, params: dict[str, Any], timeout: float):
        nonlocal called_count
        called_count += 1
        raise httpx.TimeoutException("timeout")

    monkeypatch.setattr(ndl_client.httpx, "get", fake_get)
    request_policy = ndl_client.NdlRequestPolicy(timeout_seconds=10.0, max_retries=2)
    client = ndl_client.NdlClient(base_url="https://example.com/ndl", request_policy=request_policy)

    with pytest.raises(HTTPException) as error_info:
        client.fetch_catalog_volume_metadata("9780000000123")

    assert called_count == 3
    assert error_info.value.status_code == 504
    assert error_info.value.detail == {
        "code": "NDL_API_TIMEOUT",
        "message": "NDL API request timed out",
        "details": {"upstream": "NDL Search", "timeoutSeconds": 10},
    }


def test_ndl_client_retries_retryable_status_and_succeeds(monkeypatch):
    """再試行対象ステータスは方針回数内でリトライして成功できる."""
    called_count = 0
    xml_text = """
    <rss xmlns:dc="http://purl.org/dc/elements/1.1/">
      <channel>
        <item>
          <dc:title>リトライ作品 第1巻</dc:title>
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

    with pytest.raises(HTTPException) as error_info:
        client.fetch_catalog_volume_metadata("9780000000123")

    assert called_count == 1
    assert error_info.value.status_code == 502
    assert error_info.value.detail == {
        "code": "NDL_API_BAD_GATEWAY",
        "message": "NDL API returned non-200 status",
        "details": {"upstream": "NDL Search", "statusCode": 400},
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
