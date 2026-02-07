import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

BACKEND_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = BACKEND_ROOT / "data" / "library.db"
DEFAULT_NDL_API_BASE_URL = "https://ndlsearch.ndl.go.jp/api/opensearch"
DEFAULT_ALLOWED_ORIGINS = ["http://localhost:3000"]
DEFAULT_API_HOST = "0.0.0.0"
DEFAULT_API_PORT = 8000
DEFAULT_API_RELOAD = True


@dataclass(frozen=True)
class Settings:
    """環境変数と既定値から解決したアプリ設定."""

    db_path: Path
    ndl_api_base_url: str
    allowed_origins: list[str]
    api_host: str
    api_port: int
    api_reload: bool


def resolve_db_path(env_value: Optional[str]) -> Path:
    """DB_PATH を解決し、未設定時はデフォルトパスを返す."""
    if not env_value:
        return DEFAULT_DB_PATH

    candidate = Path(env_value).expanduser()
    if not candidate.is_absolute():
        candidate = BACKEND_ROOT / candidate

    return candidate


def _read_bool_env(env_value: Optional[str], default_value: bool) -> bool:
    """真偽値の環境変数文字列を解釈する."""
    if env_value is None:
        return default_value

    return env_value.strip().lower() in {"1", "true", "yes", "on"}


def _read_int_env(env_value: Optional[str], default_value: int) -> int:
    """整数の環境変数文字列を解釈し、不正値は既定値へ戻す."""
    if env_value is None:
        return default_value

    try:
        return int(env_value)
    except ValueError:
        return default_value


def _resolve_allowed_origins(env_value: Optional[str]) -> list[str]:
    """ALLOWED_ORIGINS をカンマ区切りで解決する."""
    if env_value is None:
        return list(DEFAULT_ALLOWED_ORIGINS)

    origins = [origin.strip() for origin in env_value.split(",") if origin.strip()]
    if len(origins) == 0:
        return list(DEFAULT_ALLOWED_ORIGINS)

    return origins


def load_settings(env: Optional[Mapping[str, str]] = None) -> Settings:
    """環境変数を優先して設定を読み込み、未設定値は既定値で補完する."""
    source = env if env is not None else os.environ

    return Settings(
        db_path=resolve_db_path(source.get("DB_PATH")),
        ndl_api_base_url=source.get("NDL_API_BASE_URL", DEFAULT_NDL_API_BASE_URL),
        allowed_origins=_resolve_allowed_origins(source.get("ALLOWED_ORIGINS")),
        api_host=source.get("API_HOST", DEFAULT_API_HOST),
        api_port=_read_int_env(source.get("API_PORT"), DEFAULT_API_PORT),
        api_reload=_read_bool_env(source.get("API_RELOAD"), DEFAULT_API_RELOAD),
    )
