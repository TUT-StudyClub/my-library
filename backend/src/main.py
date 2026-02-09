import logging
import re
import sqlite3
import unicodedata
from collections.abc import Mapping, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Annotated, Any, Optional
from xml.etree import ElementTree as ET

import httpx
import uvicorn
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from starlette.exceptions import HTTPException as StarletteHTTPException

from src.config import load_settings
from src.db import check_database_connection, get_db_connection, initialize_database
from src.library_queries import fetch_library_series, fetch_series_detail

load_dotenv()
settings = load_settings()
logger = logging.getLogger(__name__)

DEFAULT_ERROR_CODE_BY_STATUS = {
    status.HTTP_400_BAD_REQUEST: "BAD_REQUEST",
    status.HTTP_401_UNAUTHORIZED: "UNAUTHORIZED",
    status.HTTP_403_FORBIDDEN: "FORBIDDEN",
    status.HTTP_404_NOT_FOUND: "NOT_FOUND",
    status.HTTP_409_CONFLICT: "CONFLICT",
    422: "VALIDATION_ERROR",
    status.HTTP_429_TOO_MANY_REQUESTS: "TOO_MANY_REQUESTS",
    status.HTTP_502_BAD_GATEWAY: "BAD_GATEWAY",
    status.HTTP_500_INTERNAL_SERVER_ERROR: "INTERNAL_SERVER_ERROR",
    status.HTTP_503_SERVICE_UNAVAILABLE: "SERVICE_UNAVAILABLE",
    status.HTTP_504_GATEWAY_TIMEOUT: "GATEWAY_TIMEOUT",
}


def _build_error_response(
    status_code: int,
    code: str,
    message: str,
    details: Optional[dict[str, Any]] = None,
) -> JSONResponse:
    """統一フォーマットのエラーレスポンスを構築する."""
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code,
                "message": message,
                "details": details or {},
            }
        },
    )


def _extract_error_code(status_code: int, detail: Any) -> str:
    """HTTP例外detailから code を抽出し、なければHTTPステータスで補完する."""
    if isinstance(detail, Mapping):
        code_value = detail.get("code")
        if isinstance(code_value, str) and code_value.strip():
            return code_value

    return DEFAULT_ERROR_CODE_BY_STATUS.get(status_code, "HTTP_ERROR")


def _extract_error_message(detail: Any) -> str:
    """HTTP例外detailから message を抽出し、なければ文字列化する."""
    if isinstance(detail, Mapping):
        message_value = detail.get("message")
        if isinstance(message_value, str) and message_value.strip():
            return message_value

    if isinstance(detail, str):
        stripped = detail.strip()
        if stripped != "":
            return stripped

    return "Request failed."


def _extract_error_details(detail: Any) -> dict[str, Any]:
    """HTTP例外detailから details を抽出する."""
    if isinstance(detail, Mapping):
        detail_value = detail.get("details")
        if isinstance(detail_value, dict):
            return dict(detail_value)

    return {}


def _build_validation_details(errors: Sequence[Any]) -> dict[str, Any]:
    """FastAPIのバリデーションエラーを統一フォーマット向けに変換する."""
    field_errors = []
    for item in errors:
        locations = item.get("loc", [])
        if isinstance(locations, (list, tuple)):
            field_parts = [str(location) for location in locations if location != "body"]
        else:
            field_parts = [str(locations)]

        field_errors.append(
            {
                "field": ".".join(field_parts) if field_parts else "request",
                "reason": str(item.get("msg", "invalid")),
            }
        )

    return {"fieldErrors": field_errors}


class CreateSeriesRequest(BaseModel):
    """Series 登録リクエスト."""

    title: str = Field(min_length=1)
    author: Optional[str] = None
    publisher: Optional[str] = None


class SeriesResponse(BaseModel):
    """Series レスポンス."""

    id: int
    title: str
    author: Optional[str]
    publisher: Optional[str]


class LibrarySeriesResponse(BaseModel):
    """ライブラリ一覧向けの Series レスポンス."""

    id: int
    title: str
    author: Optional[str]
    publisher: Optional[str]
    representative_cover_url: Optional[str]


class CreateVolumeRequest(BaseModel):
    """Volume 登録リクエスト."""

    isbn: str = Field(min_length=1)


class VolumeResponse(BaseModel):
    """Volume レスポンス."""

    isbn: str
    volume_number: Optional[int]
    cover_url: Optional[str]
    registered_at: str


class SeriesDetailResponse(SeriesResponse):
    """Series 詳細レスポンス."""

    volumes: list[VolumeResponse]


class CreateVolumeResponse(BaseModel):
    """Volume 登録レスポンス."""

    series: SeriesResponse
    volume: VolumeResponse


@dataclass(frozen=True)
class CatalogVolumeMetadata:
    """NDL Search から取得した巻メタデータ."""

    title: str
    author: Optional[str]
    publisher: Optional[str]
    volume_number: Optional[int]
    cover_url: Optional[str]


NDL_XML_NAMESPACES = {
    "dc": "http://purl.org/dc/elements/1.1/",
    "dcndl": "http://ndl.go.jp/dcndl/terms/",
}


def _normalize_optional_text(value: Optional[str]) -> Optional[str]:
    """空白のみを None に揃え、前後空白を除去する."""
    if value is None:
        return None

    normalized_value = value.strip()
    if normalized_value == "":
        return None

    return normalized_value


def _normalize_isbn(raw_isbn: str) -> str:
    """ISBN を保存用形式（半角数字13桁）へ正規化する."""
    normalized_isbn = unicodedata.normalize("NFKC", raw_isbn).strip()
    normalized_isbn = normalized_isbn.replace("-", "")

    if re.fullmatch(r"[0-9]{13}", normalized_isbn) is None:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "INVALID_ISBN",
                "message": "isbn must be 13 digits",
                "details": {"isbn": raw_isbn},
            },
        )

    return normalized_isbn


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


def _fetch_catalog_volume_metadata(isbn: str) -> CatalogVolumeMetadata:
    """ISBNでNDL Searchを検索し、登録に必要な巻メタデータを返す."""
    runtime_settings = load_settings()

    try:
        response = httpx.get(
            runtime_settings.ndl_api_base_url,
            params={"isbn": isbn, "cnt": 1},
            timeout=10.0,
        )
    except httpx.TimeoutException as error:
        raise HTTPException(
            status_code=504,
            detail={
                "code": "NDL_API_TIMEOUT",
                "message": "NDL API request timed out",
                "details": {"upstream": "NDL Search", "timeoutSeconds": 10},
            },
        ) from error
    except httpx.HTTPError as error:
        raise HTTPException(
            status_code=502,
            detail={
                "code": "NDL_API_BAD_GATEWAY",
                "message": "Failed to connect NDL API",
                "details": {"upstream": "NDL Search"},
            },
        ) from error

    if response.status_code != 200:
        raise HTTPException(
            status_code=502,
            detail={
                "code": "NDL_API_BAD_GATEWAY",
                "message": "NDL API returned non-200 status",
                "details": {"upstream": "NDL Search", "statusCode": response.status_code},
            },
        )

    return _parse_catalog_volume_metadata(response.text, isbn)


def _find_or_create_series(
    connection: sqlite3.Connection, title: str, author: Optional[str], publisher: Optional[str]
) -> SeriesResponse:
    """同一メタデータの Series を再利用し、無ければ新規作成する."""
    row = connection.execute(
        """
        SELECT id, title, author, publisher
        FROM series
        WHERE title = ?
          AND COALESCE(author, '') = COALESCE(?, '')
          AND COALESCE(publisher, '') = COALESCE(?, '')
        ORDER BY id ASC
        LIMIT 1;
        """,
        (title, author, publisher),
    ).fetchone()

    if row is not None:
        return SeriesResponse(id=row[0], title=row[1], author=row[2], publisher=row[3])

    cursor = connection.execute(
        """
        INSERT INTO series (title, author, publisher)
        VALUES (?, ?, ?);
        """,
        (title, author, publisher),
    )
    series_id = cursor.lastrowid
    created_row = connection.execute(
        """
        SELECT id, title, author, publisher
        FROM series
        WHERE id = ?;
        """,
        (series_id,),
    ).fetchone()

    if created_row is None:
        raise HTTPException(status_code=500, detail="failed to create series")

    return SeriesResponse(
        id=created_row[0],
        title=created_row[1],
        author=created_row[2],
        publisher=created_row[3],
    )


def _get_existing_volume_series_id(
    connection: sqlite3.Connection, normalized_isbn: str
) -> Optional[int]:
    """ISBN登録済みの場合の series_id を返す."""
    row = connection.execute(
        """
        SELECT series_id
        FROM volume
        WHERE isbn = ?;
        """,
        (normalized_isbn,),
    ).fetchone()

    if row is None:
        return None

    return int(row[0])


def _raise_volume_already_exists(normalized_isbn: str, series_id: int) -> None:
    """重複ISBNの統一エラーを送出する."""
    raise HTTPException(
        status_code=409,
        detail={
            "code": "VOLUME_ALREADY_EXISTS",
            "message": "Volume already exists",
            "details": {"isbn": normalized_isbn, "seriesId": series_id},
        },
    )


def _to_iso8601_utc(raw_timestamp: str) -> str:
    """SQLite日時文字列を ISO 8601 UTC 形式に変換する."""
    try:
        parsed = datetime.fromisoformat(raw_timestamp)
    except ValueError:
        return raw_timestamp

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)

    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _build_integrity_error_response(exception: sqlite3.IntegrityError) -> JSONResponse:
    """SQLite制約違反を統一エラーレスポンスへ変換する."""
    error_message = str(exception)

    if "UNIQUE constraint failed: volume.isbn" in error_message:
        return _build_error_response(
            status_code=409,
            code="VOLUME_ALREADY_EXISTS",
            message="Volume already exists",
            details={},
        )

    if "FOREIGN KEY constraint failed" in error_message:
        return _build_error_response(
            status_code=409,
            code="DB_CONSTRAINT_VIOLATION",
            message="Foreign key constraint failed",
            details={"constraint": "FOREIGN_KEY"},
        )

    return _build_error_response(
        status_code=409,
        code="DB_CONSTRAINT_VIOLATION",
        message="Database constraint violated",
        details={"reason": error_message},
    )


def _fetch_series_list(connection: sqlite3.Connection) -> list[SeriesResponse]:
    """DBに登録済みの Series 一覧を取得する."""
    rows = connection.execute("""
        SELECT id, title, author, publisher
        FROM series
        ORDER BY created_at DESC, id DESC;
        """).fetchall()

    return [
        SeriesResponse(id=row[0], title=row[1], author=row[2], publisher=row[3]) for row in rows
    ]


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """アプリ起動時に一度だけ DB を初期化する."""
    initialize_database()
    yield


app = FastAPI(
    title="My Library API",
    description="マンガ管理アプリケーションのバックエンドAPI",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(StarletteHTTPException)
async def handle_http_exception(
    _request: Request, exception: StarletteHTTPException
) -> JSONResponse:
    """HTTPExceptionを統一フォーマットへ変換する."""
    return _build_error_response(
        status_code=exception.status_code,
        code=_extract_error_code(exception.status_code, exception.detail),
        message=_extract_error_message(exception.detail),
        details=_extract_error_details(exception.detail),
    )


@app.exception_handler(RequestValidationError)
async def handle_validation_exception(
    _request: Request, exception: RequestValidationError
) -> JSONResponse:
    """リクエストバリデーション例外を統一フォーマットへ変換する."""
    return _build_error_response(
        status_code=422,
        code="VALIDATION_ERROR",
        message="リクエストパラメータが不正です。",
        details=_build_validation_details(exception.errors()),
    )


@app.exception_handler(sqlite3.IntegrityError)
async def handle_integrity_exception(
    _request: Request, exception: sqlite3.IntegrityError
) -> JSONResponse:
    """DB制約違反を統一フォーマットへ変換する."""
    return _build_integrity_error_response(exception)


@app.exception_handler(Exception)
async def handle_unexpected_exception(_request: Request, _exception: Exception) -> JSONResponse:
    """想定外例外を統一フォーマットへ変換する."""
    logger.exception("想定外の例外が発生しました。")
    return _build_error_response(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        code="INTERNAL_SERVER_ERROR",
        message="想定外のエラーが発生しました。",
        details={},
    )


@app.get("/")
async def root():
    """API の疎通確認用メッセージを返す."""
    return {"message": "My Library API"}


@app.get("/health")
async def health_check():
    """DB疎通を含むヘルスステータスを返す."""
    try:
        check_database_connection()
    except Exception as error:
        raise HTTPException(status_code=503, detail="Database connection failed") from error

    return {"status": "ok", "message": "API is running"}


@app.post("/api/series", response_model=SeriesResponse, status_code=status.HTTP_201_CREATED)
async def create_series(
    request_body: CreateSeriesRequest,
    connection: Annotated[sqlite3.Connection, Depends(get_db_connection)],
):
    """Series を1件登録する."""
    normalized_title = request_body.title.strip()
    if normalized_title == "":
        raise HTTPException(status_code=400, detail="title is required")

    cursor = connection.execute(
        """
        INSERT INTO series (title, author, publisher)
        VALUES (?, ?, ?);
        """,
        (normalized_title, request_body.author, request_body.publisher),
    )
    series_id = cursor.lastrowid
    row = connection.execute(
        """
        SELECT id, title, author, publisher
        FROM series
        WHERE id = ?;
        """,
        (series_id,),
    ).fetchone()

    if row is None:
        raise HTTPException(status_code=500, detail="failed to create series")

    return SeriesResponse(id=row[0], title=row[1], author=row[2], publisher=row[3])


@app.post("/api/volumes", response_model=CreateVolumeResponse, status_code=status.HTTP_201_CREATED)
async def create_volume(
    request_body: CreateVolumeRequest,
    connection: Annotated[sqlite3.Connection, Depends(get_db_connection)],
):
    """ISBN指定でSeries/Volumeを登録する."""
    normalized_isbn = _normalize_isbn(request_body.isbn)

    existing_series_id = _get_existing_volume_series_id(connection, normalized_isbn)
    if existing_series_id is not None:
        _raise_volume_already_exists(normalized_isbn, existing_series_id)

    metadata = _fetch_catalog_volume_metadata(normalized_isbn)
    series = _find_or_create_series(
        connection=connection,
        title=metadata.title,
        author=metadata.author,
        publisher=metadata.publisher,
    )

    try:
        connection.execute(
            """
            INSERT INTO volume (isbn, series_id, volume_number, cover_url)
            VALUES (?, ?, ?, ?);
            """,
            (
                normalized_isbn,
                series.id,
                metadata.volume_number,
                metadata.cover_url,
            ),
        )
    except sqlite3.IntegrityError:
        existing_series_id = _get_existing_volume_series_id(connection, normalized_isbn)
        if existing_series_id is not None:
            _raise_volume_already_exists(normalized_isbn, existing_series_id)

        raise

    row = connection.execute(
        """
        SELECT s.id, s.title, s.author, s.publisher, v.isbn, v.volume_number, v.cover_url, v.registered_at
        FROM volume v
        JOIN series s ON s.id = v.series_id
        WHERE v.isbn = ?;
        """,
        (normalized_isbn,),
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=500, detail="failed to create volume")

    return CreateVolumeResponse(
        series=SeriesResponse(
            id=row[0],
            title=row[1],
            author=row[2],
            publisher=row[3],
        ),
        volume=VolumeResponse(
            isbn=row[4],
            volume_number=row[5],
            cover_url=row[6],
            registered_at=_to_iso8601_utc(row[7]),
        ),
    )


@app.delete("/api/volumes/{isbn}")
async def delete_volume(
    isbn: str,
    connection: Annotated[sqlite3.Connection, Depends(get_db_connection)],
):
    """ISBN指定でVolumeを1件削除する."""
    normalized_isbn = _normalize_isbn(isbn)

    row = connection.execute(
        """
        SELECT series_id
        FROM volume
        WHERE isbn = ?;
        """,
        (normalized_isbn,),
    ).fetchone()
    if row is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "VOLUME_NOT_FOUND",
                "message": "Volume not found",
                "details": {"isbn": normalized_isbn},
            },
        )

    series_id = int(row[0])
    connection.execute(
        """
        DELETE FROM volume
        WHERE isbn = ?;
        """,
        (normalized_isbn,),
    )

    remaining_count_row = connection.execute(
        """
        SELECT COUNT(*)
        FROM volume
        WHERE series_id = ?;
        """,
        (series_id,),
    ).fetchone()
    remaining_volume_count = int(remaining_count_row[0]) if remaining_count_row is not None else 0

    return {
        "deleted": {
            "isbn": normalized_isbn,
            "seriesId": series_id,
            "remainingVolumeCount": remaining_volume_count,
        }
    }


@app.delete("/api/series/{series_id}/volumes")
async def delete_series_volumes(
    series_id: int,
    connection: Annotated[sqlite3.Connection, Depends(get_db_connection)],
):
    """Series配下のVolumeを含めてSeriesを物理削除する."""
    series_row = connection.execute(
        """
        SELECT id
        FROM series
        WHERE id = ?;
        """,
        (series_id,),
    ).fetchone()
    if series_row is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "SERIES_NOT_FOUND",
                "message": "Series not found",
                "details": {"seriesId": series_id},
            },
        )

    volume_count_row = connection.execute(
        """
        SELECT COUNT(*)
        FROM volume
        WHERE series_id = ?;
        """,
        (series_id,),
    ).fetchone()
    deleted_volume_count = int(volume_count_row[0]) if volume_count_row is not None else 0

    connection.execute(
        """
        DELETE FROM series
        WHERE id = ?;
        """,
        (series_id,),
    )

    return {
        "deleted": {
            "seriesId": series_id,
            "deletedVolumeCount": deleted_volume_count,
        }
    }


@app.get("/api/series", response_model=list[SeriesResponse])
async def list_series(connection: Annotated[sqlite3.Connection, Depends(get_db_connection)]):
    """登録済み Series 一覧を返す（最小読み取り例）."""
    return _fetch_series_list(connection)


@app.get("/api/library", response_model=list[LibrarySeriesResponse])
async def list_library(
    connection: Annotated[sqlite3.Connection, Depends(get_db_connection)],
    q: Optional[str] = None,
):
    """ライブラリ一覧を返す."""
    series_list = fetch_library_series(connection=connection, search_query=q)
    return [
        LibrarySeriesResponse(
            id=series.id,
            title=series.title,
            author=series.author,
            publisher=series.publisher,
            representative_cover_url=series.representative_cover_url,
        )
        for series in series_list
    ]


@app.get("/api/series/{series_id}", response_model=SeriesDetailResponse)
async def get_series(
    series_id: int,
    connection: Annotated[sqlite3.Connection, Depends(get_db_connection)],
):
    """Series を ID 指定で1件取得し、登録済み巻を返す."""
    series_detail = fetch_series_detail(connection=connection, series_id=series_id)
    if series_detail is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "SERIES_NOT_FOUND",
                "message": "Series not found",
                "details": {"seriesId": series_id},
            },
        )

    return SeriesDetailResponse(
        id=series_detail.id,
        title=series_detail.title,
        author=series_detail.author,
        publisher=series_detail.publisher,
        volumes=[
            VolumeResponse(
                isbn=volume.isbn,
                volume_number=volume.volume_number,
                cover_url=volume.cover_url,
                registered_at=_to_iso8601_utc(volume.registered_at),
            )
            for volume in series_detail.volumes
        ],
    )


def run() -> None:
    """開発用の API サーバーを起動する."""
    runtime_settings = load_settings()

    uvicorn.run(
        "src.main:app",
        host=runtime_settings.api_host,
        port=runtime_settings.api_port,
        reload=runtime_settings.api_reload,
    )


if __name__ == "__main__":
    run()
