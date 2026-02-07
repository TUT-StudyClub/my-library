from pathlib import Path

from src import config


def test_resolve_db_path_returns_default_when_env_is_missing():
    """DB_PATH 未設定時は固定のデフォルトパスを返す."""
    resolved = config.resolve_db_path(None)

    assert resolved == config.DEFAULT_DB_PATH
    assert resolved == config.BACKEND_ROOT / "data" / "library.db"


def test_resolve_db_path_resolves_relative_path_from_backend_root():
    """相対 DB_PATH は backend ルート基準で解決される."""
    resolved = config.resolve_db_path("tmp/local.db")

    assert resolved == config.BACKEND_ROOT / "tmp" / "local.db"


def test_resolve_db_path_keeps_absolute_path():
    """絶対パスの DB_PATH はそのまま使用される."""
    absolute_path = Path("/tmp/custom-library.db")
    resolved = config.resolve_db_path(str(absolute_path))

    assert resolved == absolute_path
