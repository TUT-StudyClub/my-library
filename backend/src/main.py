import os
from contextlib import asynccontextmanager

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from src.db import check_database_connection, initialize_database

load_dotenv()

DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 8000
DEFAULT_RELOAD = True


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

# CORS設定
allowed_origins = [
    origin.strip()
    for origin in os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
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


def _read_bool_env(key: str, default_value: bool) -> bool:
    """真偽値の環境変数を読み取り、未設定時は既定値を返す."""
    raw_value = os.getenv(key)
    if raw_value is None:
        return default_value

    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


def _read_port_env(key: str, default_value: int) -> int:
    """ポート番号の環境変数を読み取り、不正値なら既定値へフォールバックする."""
    raw_value = os.getenv(key)
    if raw_value is None:
        return default_value

    try:
        return int(raw_value)
    except ValueError:
        return default_value


def run() -> None:
    """開発用の API サーバーを起動する."""
    uvicorn.run(
        "src.main:app",
        host=os.getenv("API_HOST", DEFAULT_HOST),
        port=_read_port_env("API_PORT", DEFAULT_PORT),
        reload=_read_bool_env("API_RELOAD", DEFAULT_RELOAD),
    )


if __name__ == "__main__":
    run()
