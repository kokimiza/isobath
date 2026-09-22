import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest

from isobath.serve import Server, config


def test_render_port_and_single_process(monkeypatch):
    monkeypatch.setenv("PORT", "12345")
    settings = config()
    assert settings.host == "0.0.0.0"  # noqa: S104 -- verifies Render's required bind address
    assert settings.port == 12345
    assert settings.workers == 1
    assert not settings.access_log


@pytest.mark.parametrize("port", ["", "abc", "0", "65536"])
def test_invalid_port_fails_immediately(monkeypatch, port):
    monkeypatch.setenv("PORT", port)
    with pytest.raises(ValueError, match="PORT must"):
        config()


def test_shutdown_signal_is_logged(capsys, monkeypatch):
    monkeypatch.setenv("PORT", "10000")
    server = Server(config())
    server.handle_exit(signal.SIGTERM, None)
    assert server.should_exit
    assert "Shutdown requested: signal=SIGTERM" in capsys.readouterr().err


def test_direct_start_stays_alive_with_closed_stdin(monkeypatch, tmp_path):
    # Real process/socket: checks the same module Render starts, without a database.
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    monkeypatch.setenv("PORT", str(port))
    monkeypatch.setenv("DATABASE_URL", "")
    app_dir = Path(__file__).resolve().parents[1]
    with (tmp_path / "server.log").open("w+") as output:
        process = subprocess.Popen(
            [sys.executable, "-m", "isobath.serve"],
            cwd=app_dir,
            stdin=subprocess.DEVNULL,
            stdout=output,
            stderr=subprocess.STDOUT,
        )
        try:
            deadline = time.monotonic() + 15
            checks = 0
            with httpx.Client(timeout=1, trust_env=False) as client:
                while time.monotonic() < deadline and checks < 5:
                    assert process.poll() is None
                    try:
                        response = client.get(f"http://127.0.0.1:{port}/healthz")
                        assert response.status_code == 200
                        assert response.json() == {"status": "ok"}
                        checks += 1
                    except (httpx.ConnectError, httpx.TimeoutException):
                        pass
                    time.sleep(0.25)
            assert checks == 5
            assert process.poll() is None
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
