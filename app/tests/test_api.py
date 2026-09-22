"""HTTP-layer checks that need no database."""

from fastapi.testclient import TestClient

from isobath.inference.artifact import Model
from isobath.main import create_app

client = TestClient(create_app(Model(version="t", stage="UNCHARTED", item_set_version="0.1")))


def test_healthz():
    assert client.get("/healthz").json() == {"status": "ok"}


def test_me_requires_token_and_is_not_cached():
    r = client.get("/v1/me/position")
    assert r.status_code == 401
    assert r.json() == {"error": {"code": "unauthenticated", "message": "unauthenticated"}}
    assert r.headers["cache-control"] == "private, no-store"


def test_body_limit():
    r = client.post(
        "/v1/me/surveys",
        content=b"x" * (64 * 1024 + 1),
        headers={"content-type": "application/json"},
    )
    assert r.status_code == 413


def test_cors_only_allowed_origin():
    ok = client.options(
        "/v1/meta",
        headers={"origin": "http://localhost:5173", "access-control-request-method": "GET"},
    )
    bad = client.options(
        "/v1/meta",
        headers={"origin": "https://evil.example", "access-control-request-method": "GET"},
    )
    assert ok.headers.get("access-control-allow-origin") == "http://localhost:5173"
    assert "access-control-allow-origin" not in bad.headers


def test_unhandled_error_keeps_cors_headers():
    app = create_app(Model(version="t", stage="UNCHARTED", item_set_version="0.1"))

    @app.get("/boom")
    def boom():
        raise RuntimeError("boom")

    r = TestClient(app, raise_server_exceptions=False).get(
        "/boom", headers={"origin": "http://localhost:5173"}
    )
    assert r.status_code == 500
    assert r.json()["error"]["code"] == "internal_error"
    assert r.headers.get("access-control-allow-origin") == "http://localhost:5173"


def test_meta_is_not_marked_private():
    # "/v1/meta" shares the "/v1/me" prefix; only /v1/me/* is per-user
    r = client.get("/v1/meta")
    assert r.headers.get("cache-control") != "private, no-store"
