import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from src.db import check_database_connection, initialize_database

load_dotenv()


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
