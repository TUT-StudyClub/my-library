import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Optional
from xml.etree import ElementTree as ET

import httpx
from fastapi import HTTPException

from src.config import load_settings

NDL_XML_NAMESPACES = {
    "dc": "http://purl.org/dc/elements/1.1/",
    "dcndl": "http://ndl.go.jp/dcndl/terms/",
}


@dataclass(frozen=True)
class NdlRequestPolicy:
    """NDL API 呼び出し時のタイムアウト・リトライ方針."""

    timeout_seconds: float = 10.0
    max_retries: int = 1
    retryable_status_codes: tuple[int, ...] = (429, 500, 502, 503, 504)


DEFAULT_REQUEST_POLICY = NdlRequestPolicy()


@dataclass(frozen=True)
class CatalogVolumeMetadata:
    """NDL Search から取得した巻メタデータ."""

    title: str
    author: Optional[str]
    publisher: Optional[str]
    volume_number: Optional[int]
    cover_url: Optional[str]


class NdlClient:
    """NDL Search API クライアント."""

    def __init__(self, base_url: str, request_policy: NdlRequestPolicy = DEFAULT_REQUEST_POLICY):
        self._base_url = base_url
        self._request_policy = request_policy

    def fetch_catalog_volume_metadata(self, isbn: str) -> CatalogVolumeMetadata:
        """ISBNでNDL Searchを検索し、登録に必要な巻メタデータを返す."""
        for attempt_index in range(self._request_policy.max_retries + 1):
            try:
                response = httpx.get(
                    self._base_url,
                    params={"isbn": isbn, "cnt": 1},
                    timeout=self._request_policy.timeout_seconds,
                )
            except httpx.TimeoutException as error:
                if _has_retry_budget(self._request_policy.max_retries, attempt_index):
                    continue

                raise HTTPException(
                    status_code=504,
                    detail={
                        "code": "NDL_API_TIMEOUT",
                        "message": "NDL API request timed out",
                        "details": {
                            "upstream": "NDL Search",
                            "timeoutSeconds": _format_timeout_seconds(
                                self._request_policy.timeout_seconds
                            ),
                        },
                    },
                ) from error
            except httpx.HTTPError as error:
                if _is_retryable_http_error(error) and _has_retry_budget(
                    self._request_policy.max_retries, attempt_index
                ):
                    continue

                raise HTTPException(
                    status_code=502,
                    detail={
                        "code": "NDL_API_BAD_GATEWAY",
                        "message": "Failed to connect NDL API",
                        "details": {"upstream": "NDL Search"},
                    },
                ) from error

            if response.status_code == 200:
                return _parse_catalog_volume_metadata(response.text, isbn)

            if (
                response.status_code in self._request_policy.retryable_status_codes
                and _has_retry_budget(self._request_policy.max_retries, attempt_index)
            ):
                continue

            raise HTTPException(
                status_code=502,
                detail={
                    "code": "NDL_API_BAD_GATEWAY",
                    "message": "NDL API returned non-200 status",
                    "details": {"upstream": "NDL Search", "statusCode": response.status_code},
                },
            )

        raise RuntimeError("unreachable")


def fetch_catalog_volume_metadata(isbn: str) -> CatalogVolumeMetadata:
    """設定値を使って NDL Search の巻メタデータを取得する."""
    runtime_settings = load_settings()
    ndl_client = NdlClient(base_url=runtime_settings.ndl_api_base_url)
    return ndl_client.fetch_catalog_volume_metadata(isbn)


def _has_retry_budget(max_retries: int, attempt_index: int) -> bool:
    """現在試行で再試行可能か判定する."""
    return attempt_index < max_retries


def _is_retryable_http_error(error: httpx.HTTPError) -> bool:
    """再試行対象の通信エラーか判定する."""
    return isinstance(error, httpx.TransportError)


def _format_timeout_seconds(timeout_seconds: float) -> Any:
    """エラー詳細向けにタイムアウト秒を整数優先で整形する."""
    if timeout_seconds.is_integer():
        return int(timeout_seconds)

    return timeout_seconds


def _normalize_optional_text(value: Optional[str]) -> Optional[str]:
    """空白のみを None に揃え、前後空白を除去する."""
    if value is None:
        return None

    normalized_value = value.strip()
    if normalized_value == "":
        return None

    return normalized_value


def _extract_first_non_empty_text(
    parent: ET.Element, path: str, namespaces: Optional[dict[str, str]] = None
) -> Optional[str]:
    """XMLから最初の非空文字列を取得する."""
    for node in parent.findall(path, namespaces or {}):
        if node.text is None:
            continue

        normalized_text = node.text.strip()
        if normalized_text != "":
            return normalized_text

    return None


def _extract_cover_url(item: ET.Element) -> Optional[str]:
    """RSS item の enclosure から表紙URLを抽出する."""
    enclosure = item.find("enclosure")
    if enclosure is None:
        return None

    return _normalize_optional_text(enclosure.attrib.get("url"))


def _extract_volume_number(text_value: Optional[str]) -> Optional[int]:
    """文字列から巻数として使える先頭の整数を抽出する."""
    if text_value is None:
        return None

    normalized_text = unicodedata.normalize("NFKC", text_value)
    matched = re.search(r"([0-9]+)", normalized_text)
    if matched is None:
        return None

    return int(matched.group(1))


def _split_title_and_volume_number(title: str) -> tuple[str, Optional[int]]:
    """タイトル末尾の巻数表現を分離する."""
    normalized_title = _normalize_optional_text(title)
    if normalized_title is None:
        raise HTTPException(
            status_code=502,
            detail={
                "code": "NDL_API_BAD_GATEWAY",
                "message": "NDL API returned invalid title",
                "details": {"upstream": "NDL Search"},
            },
        )

    patterns = [
        re.compile(r"^(?P<series>.+?)[\s　]*第(?P<number>[0-9]+)巻$"),
        re.compile(r"^(?P<series>.+?)[\s　]*(?P<number>[0-9]+)巻$"),
        re.compile(r"^(?P<series>.+?)[\s　]+vol\.?[\s　]*(?P<number>[0-9]+)$", re.IGNORECASE),
        re.compile(r"^(?P<series>.+?)[\s　]+(?P<number>[0-9]+)$"),
    ]

    for pattern in patterns:
        matched = pattern.match(normalized_title)
        if matched is None:
            continue

        series_title = _normalize_optional_text(matched.group("series"))
        if series_title is None:
            continue

        return series_title, int(matched.group("number"))

    return normalized_title, None


def _parse_catalog_volume_metadata(xml_text: str, isbn: str) -> CatalogVolumeMetadata:
    """NDL Search の OpenSearch XML から巻メタデータを抽出する."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as error:
        raise HTTPException(
            status_code=502,
            detail={
                "code": "NDL_API_BAD_GATEWAY",
                "message": "NDL API returned invalid XML",
                "details": {"upstream": "NDL Search"},
            },
        ) from error

    item = root.find("./channel/item")
    if item is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "CATALOG_ITEM_NOT_FOUND",
                "message": "Catalog item not found",
                "details": {"isbn": isbn},
            },
        )

    title_text = _extract_first_non_empty_text(item, "dc:title", NDL_XML_NAMESPACES)
    if title_text is None:
        title_text = _extract_first_non_empty_text(item, "title")

    if title_text is None:
        raise HTTPException(
            status_code=502,
            detail={
                "code": "NDL_API_BAD_GATEWAY",
                "message": "NDL API returned invalid title",
                "details": {"upstream": "NDL Search"},
            },
        )

    series_title, volume_number_from_title = _split_title_and_volume_number(title_text)
    volume_number = _extract_volume_number(
        _extract_first_non_empty_text(item, "dcndl:volume", NDL_XML_NAMESPACES)
    )
    if volume_number is None:
        volume_number = volume_number_from_title

    author = _extract_first_non_empty_text(item, "dc:creator", NDL_XML_NAMESPACES)
    if author is None:
        author = _extract_first_non_empty_text(item, "author")

    publisher = _extract_first_non_empty_text(item, "dc:publisher", NDL_XML_NAMESPACES)

    return CatalogVolumeMetadata(
        title=series_title,
        author=_normalize_optional_text(author),
        publisher=_normalize_optional_text(publisher),
        volume_number=volume_number,
        cover_url=_extract_cover_url(item),
    )
