import json
import sqlite3

from src.db_smoke import run_register_and_fetch_smoke


def test_run_register_and_fetch_smoke_persists_and_returns_data(monkeypatch, tmp_path):
    """登録した作品・巻がDBに保存され、取得結果ログも出力される."""
    db_path = tmp_path / "library.db"
    log_path = tmp_path / "register_fetch_result.json"
    monkeypatch.setenv("DB_PATH", str(db_path))

    result = run_register_and_fetch_smoke(log_path=log_path)

    assert result["status"] == "ok"
    assert len(result["volume"]["isbn"]) == 13
    assert log_path.exists()

    logged_result = json.loads(log_path.read_text(encoding="utf-8"))
    assert logged_result == result

    with sqlite3.connect(db_path) as connection:
        row = connection.execute(
            """
            SELECT s.title, v.isbn, v.volume_number
            FROM series s
            JOIN volume v ON v.series_id = s.id
            WHERE v.isbn = ?;
            """,
            (result["volume"]["isbn"],),
        ).fetchone()

    assert row == (
        result["series"]["title"],
        result["volume"]["isbn"],
        result["volume"]["volumeNumber"],
    )
