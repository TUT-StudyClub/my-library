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

    client = ndl_client.NdlClient(base_url="https://example.com/ndl", timeout_seconds=8.0)
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
    """NDL APIタイムアウト時に 504 の統一エラーを返す."""

    def fake_get(url: str, params: dict[str, Any], timeout: float):
        raise httpx.TimeoutException("timeout")

    monkeypatch.setattr(ndl_client.httpx, "get", fake_get)
    client = ndl_client.NdlClient(base_url="https://example.com/ndl", timeout_seconds=10.0)

    with pytest.raises(HTTPException) as error_info:
        client.fetch_catalog_volume_metadata("9780000000123")

    assert error_info.value.status_code == 504
    assert error_info.value.detail == {
        "code": "NDL_API_TIMEOUT",
        "message": "NDL API request timed out",
        "details": {"upstream": "NDL Search", "timeoutSeconds": 10},
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
                "timeout_seconds": self._timeout_seconds,
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
        "timeout_seconds": ndl_client.DEFAULT_REQUEST_TIMEOUT_SECONDS,
        "isbn": "9780000000123",
    }
    assert metadata.title == "設定確認作品"
