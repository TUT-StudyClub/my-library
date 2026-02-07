from pathlib import Path
from typing import Optional

BACKEND_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = BACKEND_ROOT / "data" / "library.db"


def resolve_db_path(env_value: Optional[str]) -> Path:
    """DB_PATH を解決し、未設定時はデフォルトパスを返す."""
    if not env_value:
        return DEFAULT_DB_PATH

    candidate = Path(env_value).expanduser()
    if not candidate.is_absolute():
        candidate = BACKEND_ROOT / candidate

    return candidate
