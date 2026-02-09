import re
import unicodedata
from typing import Any, Optional
from xml.etree import ElementTree as ET

import httpx
from pydantic import BaseModel, ConfigDict

from src.config import load_settings

NDL_XML_NAMESPACES = {
    "dc": "http://purl.org/dc/elements/1.1/",
    "dcndl": "http://ndl.go.jp/dcndl/terms/",
}
UPSTREAM_NAME = "NDL Search"


class NdlRequestPolicy(BaseModel):
    """NDL API 呼び出し時のタイムアウト・リトライ方針."""

    model_config = ConfigDict(frozen=True)

    timeout_seconds: float = 10.0
    max_retries: int = 1
    retryable_status_codes: tuple[int, ...] = (429, 500, 502, 503, 504)


DEFAULT_REQUEST_POLICY = NdlRequestPolicy()


class CatalogVolumeMetadata(BaseModel):
    """NDL Search から取得した巻メタデータ."""

    model_config = ConfigDict(frozen=True)

    title: str
    author: Optional[str] = None
    publisher: Optional[str] = None
    volume_number: Optional[int] = None
    cover_url: Optional[str] = None


class CatalogSearchCandidate(BaseModel):
    """NDL Search のキーワード検索候補."""

    model_config = ConfigDict(frozen=True)

    title: str
    author: Optional[str] = None
    publisher: Optional[str] = None
    isbn: Optional[str] = None
    volume_number: Optional[int] = None
    cover_url: Optional[str] = None


class NdlClientError(Exception):
    """NDLクライアント失敗時に統一エラー情報を保持する例外."""

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: Optional[dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = dict(details or {})

    def to_http_exception_detail(self) -> dict[str, Any]:
        """FastAPIのHTTPException detailに変換する."""
        return {
            "code": self.code,
            "message": self.message,
            "details": dict(self.details),
        }


class NdlClient:
    """NDL Search API クライアント."""

    def __init__(self, base_url: str, request_policy: NdlRequestPolicy = DEFAULT_REQUEST_POLICY):
        self._base_url = base_url
        self._request_policy = request_policy

    def fetch_catalog_volume_metadata(self, isbn: str) -> CatalogVolumeMetadata:
        """ISBNでNDL Searchを検索し、登録に必要な巻メタデータを返す."""
        xml_text = self._fetch_xml(params={"isbn": isbn, "cnt": 1})
        return _parse_catalog_volume_metadata(xml_text, isbn)

    def search_by_keyword(
        self, q: str, limit: int = 10, page: int = 1
    ) -> list[CatalogSearchCandidate]:
        """キーワードでNDL Searchを検索し、候補一覧を返す."""
        normalized_query = _normalize_optional_text(q)
        if normalized_query is None:
            raise ValueError("q must not be empty")

        if limit < 1:
            raise ValueError("limit must be greater than 0")

        if page < 1:
            raise ValueError("page must be greater than 0")

        start_index = (page - 1) * limit + 1
        xml_text = self._fetch_xml(
            params={
                "any": normalized_query,
                "cnt": limit,
                "idx": start_index,
            }
        )
        return _parse_catalog_search_candidates(xml_text)

    def lookup_by_identifier(self, isbn: str) -> Optional[CatalogSearchCandidate]:
        """識別子（ISBN）でNDL Searchを検索し、最良候補1件を返す."""
        normalized_isbn = _normalize_identifier(isbn)

        xml_text = self._fetch_xml(
            params={
                "isbn": normalized_isbn,
                "cnt": 10,
            }
        )
        candidates = _parse_catalog_search_candidates(xml_text)
        return _select_best_identifier_candidate(candidates, normalized_isbn)

    def _fetch_xml(self, params: dict[str, Any]) -> str:
        """再試行方針に従って XML レスポンス文字列を取得する."""
        for attempt_index in range(self._request_policy.max_retries + 1):
            try:
                response = httpx.get(
                    self._base_url,
                    params=params,
                    timeout=self._request_policy.timeout_seconds,
                )
            except httpx.TimeoutException as error:
                if _has_retry_budget(self._request_policy.max_retries, attempt_index):
                    continue

                raise NdlClientError(
                    status_code=504,
                    code="NDL_API_TIMEOUT",
                    message="NDL API request timed out",
                    details=_build_external_failure_details(
                        failure_type="timeout",
                        retryable=True,
                        timeout_seconds=_format_timeout_seconds(
                            self._request_policy.timeout_seconds
                        ),
                    ),
                ) from error
            except httpx.HTTPError as error:
                if _is_retryable_http_error(error) and _has_retry_budget(
                    self._request_policy.max_retries, attempt_index
                ):
                    continue

                retryable = _is_retryable_http_error(error)
                raise NdlClientError(
                    status_code=502,
                    code="NDL_API_BAD_GATEWAY",
                    message="Failed to connect NDL API",
                    details=_build_external_failure_details(
                        failure_type="communication", retryable=retryable
                    ),
                ) from error

            if response.status_code == 200:
                return response.text

            if (
                response.status_code in self._request_policy.retryable_status_codes
                and _has_retry_budget(self._request_policy.max_retries, attempt_index)
            ):
                continue

            retryable = response.status_code in self._request_policy.retryable_status_codes
            raise NdlClientError(
                status_code=502,
                code="NDL_API_BAD_GATEWAY",
                message="NDL API returned non-200 status",
                details=_build_external_failure_details(
                    failure_type="invalidResponse",
                    retryable=retryable,
                    status_code=response.status_code,
                ),
            )

        raise RuntimeError("unreachable")


def fetch_catalog_volume_metadata(isbn: str) -> CatalogVolumeMetadata:
    """設定値を使って NDL Search の巻メタデータを取得する."""
    runtime_settings = load_settings()
    client = NdlClient(base_url=runtime_settings.ndl_api_base_url)
    return client.fetch_catalog_volume_metadata(isbn)


def search_by_keyword(q: str, limit: int = 10, page: int = 1) -> list[CatalogSearchCandidate]:
    """設定値を使って NDL Search のキーワード候補を取得する."""
    runtime_settings = load_settings()
    client = NdlClient(base_url=runtime_settings.ndl_api_base_url)
    return client.search_by_keyword(q=q, limit=limit, page=page)


def lookup_by_identifier(isbn: str) -> Optional[CatalogSearchCandidate]:
    """設定値を使って識別子検索の最良候補1件を取得する."""
    runtime_settings = load_settings()
    client = NdlClient(base_url=runtime_settings.ndl_api_base_url)
    return client.lookup_by_identifier(isbn=isbn)


def _has_retry_budget(max_retries: int, attempt_index: int) -> bool:
    """現在試行で再試行可能か判定する."""
    return attempt_index < max_retries


def _is_retryable_http_error(error: httpx.HTTPError) -> bool:
    """再試行対象の通信エラーか判定する."""
    return isinstance(error, httpx.TransportError)


def _build_external_failure_details(
    failure_type: str,
    retryable: bool,
    timeout_seconds: Optional[Any] = None,
    status_code: Optional[int] = None,
) -> dict[str, Any]:
    """外部依存失敗の機械判定向け details を構築する."""
    details: dict[str, Any] = {
        "upstream": UPSTREAM_NAME,
        "externalFailure": True,
        "failureType": failure_type,
        "retryable": retryable,
    }
    if timeout_seconds is not None:
        details["timeoutSeconds"] = timeout_seconds
    if status_code is not None:
        details["statusCode"] = status_code
    return details


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


def _normalize_identifier(raw_identifier: str) -> str:
    """DB保存ルール相当で識別子を正規化する."""
    normalized_identifier = unicodedata.normalize("NFKC", raw_identifier).strip()
    normalized_identifier = normalized_identifier.replace("-", "")

    if re.fullmatch(r"[0-9]{13}", normalized_identifier) is None:
        raise ValueError("isbn must be 13 digits")

    return normalized_identifier


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
    """RSS item から表紙URL（または同等リンク）を抽出する."""
    for child in item:
        if _extract_xml_local_name(child.tag) != "enclosure":
            continue

        enclosure_url = _normalize_optional_text(_extract_attribute_value(child, "url"))
        if enclosure_url is not None:
            return enclosure_url

    for child in item:
        if _extract_xml_local_name(child.tag) != "link":
            continue

        cover_url_from_link = _extract_cover_url_from_link(child)
        if cover_url_from_link is not None:
            return cover_url_from_link

    for child in item:
        if _extract_xml_local_name(child.tag) not in {"thumbnail", "icon"}:
            continue

        cover_url_from_text = _normalize_optional_text(child.text)
        if cover_url_from_text is not None:
            return cover_url_from_text

    return None


def _extract_xml_local_name(qualified_name: str) -> str:
    """XMLの修飾名からローカル名を抽出する."""
    if "}" not in qualified_name:
        return qualified_name

    return qualified_name.split("}", maxsplit=1)[1]


def _extract_attribute_value(node: ET.Element, attribute_name: str) -> Optional[str]:
    """属性名を名前空間非依存で検索して値を取得する."""
    for key, value in node.attrib.items():
        if _extract_xml_local_name(key) != attribute_name:
            continue

        return value

    return None


def _extract_cover_url_from_link(link_node: ET.Element) -> Optional[str]:
    """Link 要素が書影相当リンクならURLを返す."""
    link_url = _normalize_optional_text(
        _extract_attribute_value(link_node, "href") or _extract_attribute_value(link_node, "url")
    )
    if link_url is None:
        return None

    rel_value = (_normalize_optional_text(_extract_attribute_value(link_node, "rel")) or "").lower()
    type_value = (
        _normalize_optional_text(_extract_attribute_value(link_node, "type")) or ""
    ).lower()
    lower_url = link_url.lower()

    if "thumbnail" in rel_value or "icon" in rel_value:
        return link_url

    if type_value.startswith("image/"):
        return link_url

    if "thumbnail" in lower_url or "/thumb" in lower_url or "cover" in lower_url:
        return link_url

    return None


def _extract_isbn13(text_value: Optional[str]) -> Optional[str]:
    """文字列から ISBN-13（978/979始まり）を抽出する."""
    if text_value is None:
        return None

    normalized_text = unicodedata.normalize("NFKC", text_value)
    compact_text = normalized_text.replace("-", "").replace(" ", "").replace("　", "")
    matched = re.search(r"(97[89][0-9]{10})", compact_text)
    if matched is None:
        return None

    return matched.group(1)


def _extract_isbn(item: ET.Element) -> Optional[str]:
    """RSS item から ISBN-13 を抽出する."""
    identifier_paths: list[tuple[str, Optional[dict[str, str]]]] = [
        ("dc:identifier", NDL_XML_NAMESPACES),
        ("dcndl:identifier", NDL_XML_NAMESPACES),
        ("guid", None),
        ("link", None),
    ]
    for path, namespaces in identifier_paths:
        for node in item.findall(path, namespaces or {}):
            extracted_isbn = _extract_isbn13(node.text)
            if extracted_isbn is not None:
                return extracted_isbn

    return None


def _extract_volume_number(text_value: Optional[str]) -> Optional[int]:
    """文字列から巻数として使える先頭の整数を抽出する."""
    if text_value is None:
        return None

    normalized_text = unicodedata.normalize("NFKC", text_value)
    matched = re.search(r"([0-9]+)", normalized_text)
    if matched is None:
        return None

    return int(matched.group(1))


def _select_best_identifier_candidate(
    candidates: list[CatalogSearchCandidate], normalized_isbn: str
) -> Optional[CatalogSearchCandidate]:
    """識別子検索候補から最良候補を1件選択する."""
    for candidate in candidates:
        if candidate.isbn == normalized_isbn:
            return candidate

    if len(candidates) == 0:
        return None

    return candidates[0]


def _split_title_and_volume_number(title: str) -> tuple[str, Optional[int]]:
    """タイトル末尾の巻数表現を分離する."""
    normalized_title = _normalize_optional_text(title)
    if normalized_title is None:
        raise NdlClientError(
            status_code=502,
            code="NDL_API_BAD_GATEWAY",
            message="NDL API returned invalid title",
            details=_build_external_failure_details(
                failure_type="invalidResponse",
                retryable=False,
            ),
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
        raise NdlClientError(
            status_code=502,
            code="NDL_API_BAD_GATEWAY",
            message="NDL API returned invalid XML",
            details=_build_external_failure_details(
                failure_type="invalidResponse",
                retryable=False,
            ),
        ) from error

    item = root.find("./channel/item")
    if item is None:
        raise NdlClientError(
            status_code=404,
            code="CATALOG_ITEM_NOT_FOUND",
            message="Catalog item not found",
            details={
                "isbn": isbn,
                "upstream": UPSTREAM_NAME,
                "externalFailure": False,
            },
        )

    title_text = _extract_first_non_empty_text(item, "dc:title", NDL_XML_NAMESPACES)
    if title_text is None:
        title_text = _extract_first_non_empty_text(item, "title")

    if title_text is None:
        raise NdlClientError(
            status_code=502,
            code="NDL_API_BAD_GATEWAY",
            message="NDL API returned invalid title",
            details=_build_external_failure_details(
                failure_type="invalidResponse",
                retryable=False,
            ),
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


def _parse_catalog_search_candidates(xml_text: str) -> list[CatalogSearchCandidate]:
    """NDL Search の OpenSearch XML からキーワード候補一覧を抽出する."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as error:
        raise NdlClientError(
            status_code=502,
            code="NDL_API_BAD_GATEWAY",
            message="NDL API returned invalid XML",
            details=_build_external_failure_details(
                failure_type="invalidResponse",
                retryable=False,
            ),
        ) from error

    candidates: list[CatalogSearchCandidate] = []
    for item in root.findall("./channel/item"):
        title_text = _extract_first_non_empty_text(item, "dc:title", NDL_XML_NAMESPACES)
        if title_text is None:
            title_text = _extract_first_non_empty_text(item, "title")

        if title_text is None:
            continue

        try:
            series_title, volume_number_from_title = _split_title_and_volume_number(title_text)
        except NdlClientError:
            continue

        volume_number = _extract_volume_number(
            _extract_first_non_empty_text(item, "dcndl:volume", NDL_XML_NAMESPACES)
        )
        if volume_number is None:
            volume_number = volume_number_from_title

        author = _extract_first_non_empty_text(item, "dc:creator", NDL_XML_NAMESPACES)
        if author is None:
            author = _extract_first_non_empty_text(item, "author")

        publisher = _extract_first_non_empty_text(item, "dc:publisher", NDL_XML_NAMESPACES)
        candidates.append(
            CatalogSearchCandidate(
                title=series_title,
                author=_normalize_optional_text(author),
                publisher=_normalize_optional_text(publisher),
                isbn=_extract_isbn(item),
                volume_number=volume_number,
                cover_url=_extract_cover_url(item),
            )
        )

    return candidates
