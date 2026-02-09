import logging
import re
import sqlite3
import unicodedata
from collections.abc import Mapping, Sequence
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Annotated, Any, Optional

import uvicorn
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.concurrency import run_in_threadpool
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from starlette.exceptions import HTTPException as StarletteHTTPException

from src.config import load_settings
from src.db import check_database_connection, get_db_connection, initialize_database
from src.library_queries import fetch_library_series, fetch_series_detail
from src.ndl_client import (
    CatalogSearchCandidate,
    CatalogVolumeMetadata,
    NdlClientError,
    fetch_catalog_volume_metadata,
    search_by_keyword,
)
from src.ndl_client import (
    lookup_by_identifier as ndl_lookup_by_identifier,
)

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


def _fetch_catalog_volume_metadata(isbn: str) -> CatalogVolumeMetadata:
    """ISBNでNDL Searchを検索し、登録に必要な巻メタデータを返す."""
    try:
        return fetch_catalog_volume_metadata(isbn)
    except NdlClientError as error:
        raise HTTPException(
            status_code=error.status_code,
            detail=error.to_http_exception_detail(),
        ) from error


def _search_catalog_by_keyword(q: str, limit: int) -> list[CatalogSearchCandidate]:
    """キーワードでNDL Searchを検索し、候補一覧を返す."""
    try:
        return search_by_keyword(q=q, limit=limit, page=1)
    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "INVALID_CATALOG_SEARCH_QUERY",
                "message": "Catalog search query is invalid",
                "details": {"reason": str(error)},
            },
        ) from error
    except NdlClientError as error:
        raise HTTPException(
            status_code=error.status_code,
            detail=error.to_http_exception_detail(),
        ) from error


def _lookup_catalog_by_identifier(isbn: str) -> CatalogSearchCandidate:
    """識別子でNDL Searchを検索し、最良候補1件を返す."""
    try:
        candidate = ndl_lookup_by_identifier(isbn=isbn)
    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "INVALID_ISBN",
                "message": "isbn must be 13 digits",
                "details": {"isbn": isbn, "reason": str(error)},
            },
        ) from error
    except NdlClientError as error:
        raise HTTPException(
            status_code=error.status_code,
            detail=error.to_http_exception_detail(),
        ) from error

    if candidate is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "CATALOG_ITEM_NOT_FOUND",
                "message": "Catalog item not found",
                "details": {
                    "isbn": isbn,
                    "upstream": "NDL Search",
                    "externalFailure": False,
                },
            },
        )

    return candidate


def _to_catalog_search_candidate_dto(
    candidate: CatalogSearchCandidate,
) -> CatalogSearchCandidate:
    """カタログ候補をAPIレスポンスDTOへ変換する."""
    return CatalogSearchCandidate(
        title=candidate.title,
        author=candidate.author,
        publisher=candidate.publisher,
        isbn=candidate.isbn,
        volume_number=candidate.volume_number,
        cover_url=candidate.cover_url,
    )


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

    metadata: CatalogVolumeMetadata = await run_in_threadpool(
        _fetch_catalog_volume_metadata, normalized_isbn
    )
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


@app.get("/api/catalog/search", response_model=list[CatalogSearchCandidate])
async def search_catalog(
    q: str,
    limit: Annotated[int, Query(ge=1, le=100)] = 10,
):
    """外部カタログをキーワード検索し、候補一覧を返す."""
    candidates: list[CatalogSearchCandidate] = await run_in_threadpool(
        _search_catalog_by_keyword, q, limit
    )
    return [_to_catalog_search_candidate_dto(candidate) for candidate in candidates]


@app.get("/api/catalog/lookup", response_model=CatalogSearchCandidate)
async def lookup_catalog(isbn: str):
    """外部カタログを識別子検索し、最良候補1件を返す."""
    normalized_isbn = _normalize_isbn(isbn)
    candidate: CatalogSearchCandidate = await run_in_threadpool(
        _lookup_catalog_by_identifier, normalized_isbn
    )
    return _to_catalog_search_candidate_dto(candidate)


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
