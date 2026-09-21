"""RLS / constraint / API integration against a real PostgreSQL (acceptance criteria 3, 4, 8).

    docker run -d --name isobath-pg -e POSTGRES_PASSWORD=postgres -p 55432:5432 postgres:16
    ISOBATH_TEST_PG=postgresql://postgres:postgres@127.0.0.1:55432/postgres uv run pytest

Skipped when ISOBATH_TEST_PG is not set. The test database is recreated on each run.
"""

import os
import uuid
from pathlib import Path

import psycopg
import pytest
from fastapi import Request
from fastapi.testclient import TestClient

ADMIN_URL = os.environ.get("ISOBATH_TEST_PG")
pytestmark = pytest.mark.skipif(not ADMIN_URL, reason="ISOBATH_TEST_PG not set")

ROOT = Path(__file__).resolve().parents[2]
MIGRATIONS = sorted((ROOT / "supabase" / "migrations").glob("*.sql"))
STUB = Path(__file__).parent / "db" / "supabase_stub.sql"
DB = "isobath_test"


def _url(base: str, db: str, user: str | None = None, password: str | None = None) -> str:
    info = psycopg.conninfo.conninfo_to_dict(base)
    info["dbname"] = db
    if user:
        info["user"], info["password"] = user, password
    return psycopg.conninfo.make_conninfo(**info)


@pytest.fixture(scope="module")
def admin():
    with psycopg.connect(ADMIN_URL, autocommit=True) as c:
        c.execute(f"drop database if exists {DB} with (force)")
        c.execute(f"create database {DB}")
    conn = psycopg.connect(_url(ADMIN_URL, DB), autocommit=True)
    conn.execute(STUB.read_text("utf-8"))
    for m in MIGRATIONS:
        conn.execute(m.read_text("utf-8"))
    conn.execute("alter role isobath_api password 'test'")
    # tiny bank: 6 anchors, 4 blocks x 3 items, 1 attention check
    qid = 1
    for i in range(6):
        conn.execute(
            "insert into app.questions (id, code, item_set_version, kind, anchor, status, text_ja)"
            " values (%s, %s, '0.1', 'personality', true, 'candidate', 'q')",
            (qid, f"A{i}"),
        )
        qid += 1
    for b in range(4):
        for i in range(3):
            conn.execute(
                "insert into app.questions (id, code, item_set_version, kind, block_no, status,"
                " text_ja) values (%s, %s, '0.1', 'personality', %s, 'candidate', 'q')",
                (qid, f"B{b}-{i}", b),
            )
            qid += 1
    conn.execute(
        "insert into app.questions (id, code, item_set_version, kind, status, quality_rule, text_ja)"
        """ values (%s, 'QA', '0.1', 'quality', 'candidate', '{"type":"attention","expect":4}', 'q')""",
        (qid,),
    )
    yield conn
    conn.close()


@pytest.fixture(scope="module")
def api(admin):
    os.environ["DATABASE_URL"] = _url(ADMIN_URL, DB, "isobath_api", "test")
    from isobath import db
    from isobath.auth import current_claims
    from isobath.config import get_settings
    from isobath.inference.artifact import Model
    from isobath.main import create_app

    get_settings.cache_clear()
    db.pool.cache_clear()
    app = create_app(Model(version="t", stage="UNCHARTED", item_set_version="0.1"))

    def claims_from_header(request: Request) -> dict:
        sub = request.headers["x-test-user"]
        return {"sub": sub, "role": "authenticated", "aud": "authenticated"}

    app.dependency_overrides[current_claims] = claims_from_header

    def as_user(uid):
        return TestClient(app, headers={"x-test-user": str(uid)})

    yield as_user
    db.pool().close()


def new_user(admin) -> uuid.UUID:
    return admin.execute("insert into auth.users default values returning id").fetchone()[0]


CONSENTS = {
    "consents": [
        {"document": "terms", "version": "1"},
        {"document": "privacy", "version": "1"},
        {"document": "research", "version": "1"},
    ]
}


def test_full_flow_and_isolation(admin, api):
    a, b = new_user(admin), new_user(admin)

    ca = api(a)
    assert ca.post("/v1/me/surveys", json={"kind": "initial"}).status_code == 403  # no consent
    assert ca.post("/v1/me/consents", json=CONSENTS).status_code == 204
    s = ca.post("/v1/me/surveys", json={"kind": "initial"})
    assert s.status_code == 201
    sid, total = s.json()["id"], s.json()["total"]
    assert total == 6 + 3 * 3 + 1
    assert ca.post("/v1/me/surveys", json={"kind": "initial"}).json()["id"] == sid  # reuse open

    qs = ca.get("/v1/me/surveys/current").json()["questions"]
    assigned = {q["id"] for q in qs}
    unassigned = next(q for q in range(1, 20) if q not in assigned)

    r = ca.post(
        f"/v1/me/surveys/{sid}/answers", json={"answers": [{"question_id": unassigned, "value": 3}]}
    )
    assert r.status_code == 422 and r.json()["error"]["code"] == "question_not_assigned"
    r = ca.post(
        f"/v1/me/surveys/{sid}/answers",
        json={"answers": [{"question_id": qs[0]["id"], "value": 6}]},
    )
    assert r.status_code == 422
    first = {"answers": [{"question_id": qs[0]["id"], "value": 3, "response_ms": 2000}]}
    assert ca.post(f"/v1/me/surveys/{sid}/answers", json=first).status_code == 204
    assert ca.post(f"/v1/me/surveys/{sid}/answers", json=first).status_code == 409
    assert ca.post(f"/v1/me/surveys/{sid}/complete").status_code == 409  # unanswered remain

    # B cannot see or write A's session
    cb = api(b)
    assert cb.post(f"/v1/me/surveys/{sid}/answers", json=first).status_code == 404
    assert cb.get("/v1/me/surveys/current").status_code == 404

    rest = [{"question_id": q["id"], "value": 4, "response_ms": 2500} for q in qs[1:]]
    assert ca.post(f"/v1/me/surveys/{sid}/answers", json={"answers": rest}).status_code == 204
    done = ca.post(f"/v1/me/surveys/{sid}/complete")
    assert done.status_code == 200 and done.json()["stage"] == "UNCHARTED"
    pos = ca.get("/v1/me/position").json()
    assert "position" not in pos and pos["observer_no"] >= 1


def test_rls_blocks_direct_sql(admin, api):
    from isobath.db import pool, user_tx

    a, b = new_user(admin), new_user(admin)
    api(a).post("/v1/me/consents", json=CONSENTS)
    sid = api(a).post("/v1/me/surveys", json={"kind": "initial"}).json()["id"]
    qid = admin.execute(
        "select question_id from app.survey_session_questions where session_id = %s limit 1", (sid,)
    ).fetchone()[0]

    claims_b = {"sub": str(b), "role": "authenticated"}
    with user_tx(claims_b) as conn:
        assert conn.execute("select count(*) n from app.survey_sessions").fetchone()["n"] == 0
        assert (
            conn.execute("select count(*) n from app.survey_session_questions").fetchone()["n"] == 0
        )

    with pytest.raises(psycopg.errors.InsufficientPrivilege), user_tx(claims_b) as conn:
        conn.execute(  # pretend to be A
            "insert into app.answers (session_id, user_id, question_id, value) values (%s,%s,%s,3)",
            (sid, a, qid),
        )
    # own user_id on A's session: RLS (session not visible) or the composite FK rejects it
    rejected = (psycopg.errors.InsufficientPrivilege, psycopg.errors.ForeignKeyViolation)
    with pytest.raises(rejected), user_tx(claims_b) as conn:
        conn.execute(
            "insert into app.answers (session_id, user_id, question_id, value) values (%s,%s,%s,3)",
            (sid, b, qid),
        )

    # isobath_api without SET ROLE has no table access (fail closed)
    with pytest.raises(psycopg.errors.InsufficientPrivilege), pool().connection() as conn:
        conn.execute("select 1 from app.answers")

    # tombstones / audit are invisible to users
    with pytest.raises(psycopg.errors.InsufficientPrivilege), user_tx(claims_b) as conn:
        conn.execute("select 1 from app.deletion_tombstones")


def test_delete_me(admin, api):
    a = new_user(admin)
    c = api(a)
    c.post("/v1/me/consents", json=CONSENTS)
    c.post("/v1/me/surveys", json={"kind": "initial"})
    pseudo = admin.execute(
        "select pseudo_id from app.profiles where user_id = %s", (a,)
    ).fetchone()[0]

    assert c.delete("/v1/me").status_code == 204
    for table in ("profiles", "consents", "survey_sessions", "survey_session_questions"):
        n = admin.execute(f"select count(*) from app.{table} where user_id = %s", (a,)).fetchone()[
            0
        ]
        assert n == 0, table
    assert admin.execute("select count(*) from auth.users where id = %s", (a,)).fetchone()[0] == 0
    assert (
        admin.execute(
            "select count(*) from app.deletion_tombstones where pseudo_id = %s", (pseudo,)
        ).fetchone()[0]
        == 1
    )


def test_meta_uses_public_stats_only(api):
    r = api(uuid.uuid4()).get("/v1/meta")
    assert r.status_code == 200 and r.json()["participants"] >= 1
