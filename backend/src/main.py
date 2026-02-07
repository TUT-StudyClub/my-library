import sqlite3
from contextlib import asynccontextmanager
from typing import Annotated, Optional

import uvicorn
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from src.config import load_settings
from src.db import check_database_connection, get_db_connection, initialize_database

load_dotenv()
settings = load_settings()


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
