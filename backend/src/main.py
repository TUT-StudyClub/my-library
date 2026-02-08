import logging
import sqlite3
from collections.abc import Mapping, Sequence
from contextlib import asynccontextmanager
from typing import Annotated, Any, Optional

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
    status.HTTP_500_INTERNAL_SERVER_ERROR: "INTERNAL_SERVER_ERROR",
    status.HTTP_503_SERVICE_UNAVAILABLE: "SERVICE_UNAVAILABLE",
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


@app.get("/api/series", response_model=list[SeriesResponse])
async def list_series(connection: Annotated[sqlite3.Connection, Depends(get_db_connection)]):
    """登録済み Series 一覧を返す（最小読み取り例）."""
    return _fetch_series_list(connection)


@app.get("/api/series/{series_id}", response_model=SeriesResponse)
async def get_series(
    series_id: int,
    connection: Annotated[sqlite3.Connection, Depends(get_db_connection)],
):
    """Series を ID 指定で1件取得する."""
    row = connection.execute(
        """
        SELECT id, title, author, publisher
        FROM series
        WHERE id = ?;
        """,
        (series_id,),
    ).fetchone()

    if row is None:
        raise HTTPException(status_code=404, detail="Series not found")

    return SeriesResponse(id=row[0], title=row[1], author=row[2], publisher=row[3])


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
