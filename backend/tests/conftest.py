import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import httpx
import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


class MockNdlApi:
    """NDL API 呼び出しの結果を順番にモックするテスト用ヘルパー."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch):
        self.calls: list[dict[str, Any]] = []
        self._queue: list[Any] = []
        from src import ndl_client

        self._ndl_client = ndl_client
        monkeypatch.setattr(self._ndl_client.httpx, "get", self._fake_get)

    def enqueue_response(self, status_code: int, text: str = "") -> None:
        """HTTPステータス付きレスポンスを1件追加する."""
        self._queue.append(SimpleNamespace(status_code=status_code, text=text))

    def enqueue_timeout(self, message: str = "timeout") -> None:
        """タイムアウト例外を1件追加する."""
        self._queue.append(httpx.TimeoutException(message))

    def enqueue_connect_error(self, message: str = "connect failed") -> None:
        """通信失敗例外を1件追加する."""
        request = httpx.Request("GET", "https://example.com/ndl")
        self._queue.append(httpx.ConnectError(message, request=request))

    def _fake_get(self, url: str, params: dict[str, Any], timeout: float):
        self.calls.append({"url": url, "params": params, "timeout": timeout})
        if len(self._queue) == 0:
            raise AssertionError(
                "MockNdlApi queue is empty. enqueue_response/enqueue_timeout を設定してください。"
            )

        queued = self._queue.pop(0)
        if isinstance(queued, Exception):
            raise queued

        return queued


@pytest.fixture
def mock_ndl_api(monkeypatch: pytest.MonkeyPatch) -> MockNdlApi:
    """NDL API（httpx.get）を順序付きで差し替える."""
    return MockNdlApi(monkeypatch)
