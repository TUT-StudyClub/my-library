import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

app = FastAPI(
    title="My Library API",
    description="マンガ管理アプリケーションのバックエンドAPI",
    version="0.1.0",
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
    """Return a simple API greeting."""
    return {"message": "My Library API"}


@app.get("/health")
async def health_check():
    """Return health status for readiness checks."""
    return {"status": "ok", "message": "API is running"}
