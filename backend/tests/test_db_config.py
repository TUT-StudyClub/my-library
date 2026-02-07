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


def test_load_settings_returns_defaults_when_env_is_missing():
    """未設定時は各設定項目が既定値で解決される."""
    settings = config.load_settings(env={})

    assert settings.db_path == config.DEFAULT_DB_PATH
    assert settings.ndl_api_base_url == config.DEFAULT_NDL_API_BASE_URL
    assert settings.allowed_origins == config.DEFAULT_ALLOWED_ORIGINS
    assert settings.api_host == config.DEFAULT_API_HOST
    assert settings.api_port == config.DEFAULT_API_PORT
    assert settings.api_reload is config.DEFAULT_API_RELOAD


def test_load_settings_resolves_env_values():
    """環境変数がある場合は上書き値を優先して解決する."""
    settings = config.load_settings(
        env={
            "DB_PATH": "tmp/custom.db",
            "NDL_API_BASE_URL": "https://example.com/ndl",
            "ALLOWED_ORIGINS": "https://example.com, http://localhost:3000 ",
            "API_HOST": "127.0.0.1",
            "API_PORT": "9000",
            "API_RELOAD": "false",
        }
    )

    assert settings.db_path == config.BACKEND_ROOT / "tmp" / "custom.db"
    assert settings.ndl_api_base_url == "https://example.com/ndl"
    assert settings.allowed_origins == ["https://example.com", "http://localhost:3000"]
    assert settings.api_host == "127.0.0.1"
    assert settings.api_port == 9000
    assert settings.api_reload is False


def test_load_settings_falls_back_to_default_when_env_value_is_invalid():
    """不正な設定値は既定値にフォールバックする."""
    settings = config.load_settings(
        env={
            "ALLOWED_ORIGINS": " , ",
            "API_PORT": "invalid",
        }
    )

    assert settings.allowed_origins == config.DEFAULT_ALLOWED_ORIGINS
    assert settings.api_port == config.DEFAULT_API_PORT
