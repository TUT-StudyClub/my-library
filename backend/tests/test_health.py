import sqlite3

from fastapi.testclient import TestClient

from src import main


def test_health_returns_ok_when_database_is_available(monkeypatch, tmp_path):
    """DBチェック成功時に health が正常応答を返す."""
    monkeypatch.setenv("DB_PATH", str(tmp_path / "health.db"))

    with TestClient(main.app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "message": "API is running"}


def test_health_returns_503_when_database_check_fails(monkeypatch, tmp_path):
    """DBチェック失敗時に health が 503 を返す."""
    monkeypatch.setenv("DB_PATH", str(tmp_path / "health.db"))

    def raise_connection_error():
        raise sqlite3.OperationalError("database is unavailable")

    monkeypatch.setattr(main, "check_database_connection", raise_connection_error)

    with TestClient(main.app) as client:
        response = client.get("/health")

    assert response.status_code == 503
    assert response.json() == {"detail": "Database connection failed"}
