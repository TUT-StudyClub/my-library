from src import main


def test_run_uses_default_server_config(monkeypatch):
    """環境変数未設定時は既定の起動設定で uvicorn.run を呼ぶ."""
    monkeypatch.delenv("API_HOST", raising=False)
    monkeypatch.delenv("API_PORT", raising=False)
    monkeypatch.delenv("API_RELOAD", raising=False)

    called = {}

    def fake_run(app_path: str, host: str, port: int, reload: bool) -> None:
        called.update({"app_path": app_path, "host": host, "port": port, "reload": reload})

    monkeypatch.setattr(main.uvicorn, "run", fake_run)

    main.run()

    assert called == {
        "app_path": "src.main:app",
        "host": "0.0.0.0",
        "port": 8000,
        "reload": True,
    }


def test_run_uses_env_override_server_config(monkeypatch):
    """環境変数が設定されている場合は上書き値で uvicorn.run を呼ぶ."""
    monkeypatch.setenv("API_HOST", "127.0.0.1")
    monkeypatch.setenv("API_PORT", "9000")
    monkeypatch.setenv("API_RELOAD", "false")

    called = {}

    def fake_run(app_path: str, host: str, port: int, reload: bool) -> None:
        called.update({"app_path": app_path, "host": host, "port": port, "reload": reload})

    monkeypatch.setattr(main.uvicorn, "run", fake_run)

    main.run()

    assert called == {
        "app_path": "src.main:app",
        "host": "127.0.0.1",
        "port": 9000,
        "reload": False,
    }


def test_run_falls_back_default_port_when_api_port_is_invalid(monkeypatch):
    """API_PORT が不正な場合は既定ポートにフォールバックする."""
    monkeypatch.delenv("API_HOST", raising=False)
    monkeypatch.setenv("API_PORT", "invalid")
    monkeypatch.delenv("API_RELOAD", raising=False)

    called = {}

    def fake_run(app_path: str, host: str, port: int, reload: bool) -> None:
        called.update({"app_path": app_path, "host": host, "port": port, "reload": reload})

    monkeypatch.setattr(main.uvicorn, "run", fake_run)

    main.run()

    assert called == {
        "app_path": "src.main:app",
        "host": "0.0.0.0",
        "port": 8000,
        "reload": True,
    }
