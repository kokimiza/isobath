"""RLS / constraint / API integration against a real PostgreSQL (acceptance criteria 3, 4, 8).

    docker run -d --name isobath-pg -e POSTGRES_PASSWORD=postgres -p 55432:5432 postgres:16
    ISOBATH_TEST_PG=postgresql://postgres:postgres@127.0.0.1:55432/postgres uv run pytest

Skipped when ISOBATH_TEST_PG is not set. The test database is recreated on each run.
"""

import os
import uuid
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

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
LEGACY_USER = uuid.UUID("6ab3ccf8-531f-4e48-bf07-5db3441d7e80")


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
    # Supabase accounts may predate our schema and its signup trigger.
    conn.execute("insert into auth.users (id) values (%s)", (LEGACY_USER,))
    for m in MIGRATIONS:
        conn.execute(m.read_text("utf-8"))
    conn.execute("alter role isobath_api password 'test'")
    conn.execute("alter role isobath_batch password 'test'")
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


REQUIRED = [{"document": "terms", "version": "1"}, {"document": "privacy", "version": "1"}]
CONSENTS = {"consents": [*REQUIRED, {"document": "research", "version": "1"}]}


def test_existing_account_can_consent_and_start_survey(admin, api):
    c = api(LEGACY_USER)
    identity = admin.execute(
        "select pseudo_id, observer_no from app.profiles where user_id = %s", (LEGACY_USER,)
    ).fetchone()
    assert identity is not None
    assert not c.get("/v1/me/consents").json()["complete"]
    assert c.post("/v1/me/consents", json={"consents": REQUIRED}).status_code == 204
    status = c.get("/v1/me/consents").json()
    assert status["complete"]
    assert not status["research"]  # backfill must never opt users into research
    assert c.get("/v1/me/position").status_code == 200
    assert c.post("/v1/me/surveys", json={"kind": "initial"}).status_code == 201
    # A retry of the repair preserves both identity and recorded consent.
    repair = ROOT / "supabase/migrations/20260922010000_backfill_profiles.sql"
    admin.execute(repair.read_text("utf-8"))
    assert (
        admin.execute(
            "select pseudo_id, observer_no from app.profiles where user_id = %s", (LEGACY_USER,)
        ).fetchone()
        == identity
    )
    assert c.get("/v1/me/consents").json() == status


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
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "question_not_assigned"
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
    assert done.status_code == 200
    assert done.json()["next_update_at"].endswith("16:00:00Z")  # 01:00 JST
    pos = ca.get("/v1/me/position").json()
    assert "position" not in pos
    assert pos["observer_no"] >= 1
    assert pos["pending"]  # not reflected until the nightly batch (FR-POS-07)
    # one survey per nightly window (FR-CON-05)
    too_soon = ca.post("/v1/me/surveys", json={"kind": "continuous"})
    assert too_soon.status_code == 429


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
    for table in ("profiles", "survey_sessions", "survey_session_questions"):
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


def test_meta_before_first_batch(api):
    from isobath import runs

    runs._cache["at"] = float("-inf")
    body = api(uuid.uuid4()).get("/v1/meta").json()
    assert body["updated_at"] is None
    assert body["next_update_at"].endswith("16:00:00Z")


def _answer_all(client, sid):
    qs = client.get("/v1/me/surveys/current").json()["questions"]
    answers = [{"question_id": q["id"], "value": 3, "response_ms": 2500} for q in qs]
    assert (
        client.post(f"/v1/me/surveys/{sid}/answers", json={"answers": answers}).status_code == 204
    )
    assert client.post(f"/v1/me/surveys/{sid}/complete").status_code == 200


def _in_analysis(admin, uid) -> bool:
    pseudo = admin.execute(
        "select pseudo_id from app.profiles where user_id = %s", (uid,)
    ).fetchone()
    return bool(
        admin.execute(
            "select count(*) from analysis.responses where pseudo_id = %s", (pseudo[0],)
        ).fetchone()[0]
    )


def test_research_is_optional_and_withdrawable(admin, api):
    u = new_user(admin)
    c = api(u)
    # required consents only: the service works, but nothing reaches the analysis
    assert c.post("/v1/me/consents", json={"consents": REQUIRED}).status_code == 204
    status = c.get("/v1/me/consents").json()
    assert status["complete"]
    assert not status["research"]
    sid = c.post("/v1/me/surveys", json={"kind": "initial"}).json()["id"]
    _answer_all(c, sid)
    assert not _in_analysis(admin, u)

    # join -> included; withdraw (account kept) -> excluded again, answers kept for the user
    assert c.put("/v1/me/research", json={"participating": True}).status_code == 204
    assert _in_analysis(admin, u)
    assert c.put("/v1/me/research", json={"participating": False}).status_code == 204
    assert not _in_analysis(admin, u)
    assert c.get("/v1/me/position").json()["survey"]["initial_completed"]
    actions = admin.execute(
        "select action from app.consent_events where user_id = %s and document = 'research'"
        " order by id",
        (u,),
    ).fetchall()
    assert [a for (a,) in actions] == ["grant", "withdraw"]


def test_consent_events_are_append_only(admin, api):
    from isobath.db import user_tx

    u = new_user(admin)
    api(u).post("/v1/me/consents", json=CONSENTS)
    claims = {"sub": str(u), "role": "authenticated"}
    for sql in (
        "update app.consent_events set action = 'withdraw'",
        "delete from app.consent_events",
    ):
        with pytest.raises(psycopg.errors.InsufficientPrivilege), user_tx(claims) as conn:
            conn.execute(sql)


# --- nightly batch (requirements §4.1) -------------------------------------------------------

JST = ZoneInfo("Asia/Tokyo")


def _completed_user(admin, api, completed_at: datetime, research: bool = True) -> uuid.UUID:
    u = new_user(admin)
    c = api(u)
    c.post("/v1/me/consents", json=CONSENTS if research else {"consents": REQUIRED})
    sid = c.post("/v1/me/surveys", json={"kind": "initial"}).json()["id"]
    _answer_all(c, sid)
    admin.execute(
        "update app.survey_sessions set completed_at = %s where id = %s", (completed_at, sid)
    )
    return u


def test_nightly_cutoff_idempotency_and_api(admin, api):
    from conftest import synthetic_model

    from isobath import nightly, runs

    admin.execute("delete from app.batch_runs")
    dsn = _url(ADMIN_URL, DB, "isobath_batch", "test")
    model = synthetic_model()  # question ids 1..60 cover the test bank

    before = _completed_user(admin, api, datetime(2030, 3, 15, 0, 59, 59, tzinfo=JST))
    after = _completed_user(admin, api, datetime(2030, 3, 15, 1, 0, 0, tzinfo=JST))
    quiet = _completed_user(admin, api, datetime(2030, 3, 14, 12, 0, tzinfo=JST), research=False)

    # started late (01:40) and still processes exactly [.., 01:00) of 3/15
    first = nightly.run(dsn, model, datetime(2030, 3, 15, 1, 40, tzinfo=JST), k=1)
    assert first["status"] == "succeeded"
    assert first["cutoff_at"] == "2030-03-14T16:00:00Z"
    snap = "select user_id from app.position_snapshots where cutoff_at = %s"
    placed = {r[0] for r in admin.execute(snap, (datetime(2030, 3, 15, 1, tzinfo=JST),))}
    assert before in placed
    assert quiet in placed  # non-participants still get their own position
    assert after not in placed  # completed at 01:00:00 -> next window

    # map counts only research participants
    run_row = admin.execute(
        "select map, participants from app.batch_runs where cutoff_at = %s",
        (datetime(2030, 3, 15, 1, tzinfo=JST),),
    ).fetchone()
    participants = {
        r[0]
        for r in admin.execute(
            """select user_id from (
                 select distinct on (user_id) user_id, action from app.consent_events
                 where document = 'research' and user_id is not null order by user_id, id desc
               ) r where action = 'grant'"""
        )
    }
    assert quiet not in participants
    assert sum(map(sum, run_row[0]["counts"])) == len(placed & participants)

    # rerun of the same cutoff (e.g. the 01:30 guard trigger) does nothing
    again = nightly.run(dsn, model, datetime(2030, 3, 15, 2, 0, tzinfo=JST), k=1)
    assert again["status"] == "skipped"

    # next night: only the new session is placed; nobody else is re-placed
    second = nightly.run(dsn, model, datetime(2030, 3, 16, 1, 5, tzinfo=JST), k=1)
    assert second["placed"] == 1
    placed2 = {r[0] for r in admin.execute(snap, (datetime(2030, 3, 16, 1, tzinfo=JST),))}
    assert placed2 == {after}

    # the API shows the batch result, not the repository's model
    runs._cache["at"] = float("-inf")
    meta = api(uuid.uuid4()).get("/v1/meta").json()
    assert meta["chart"]["stage"] == "SEED"
    assert meta["updated_at"] == "2030-03-15T16:00:00Z"
    pos = api(after).get("/v1/me/position").json()
    assert pos["pending"] is False
    assert len(pos["position"]) == 2
    chart = api(uuid.uuid4()).get("/v1/chart/current")
    assert chart.status_code == 200
    assert chart.headers["cache-control"].startswith("public, max-age=")
    admin.execute("delete from app.batch_runs")
    runs._cache["at"] = float("-inf")


def test_batch_role_cannot_touch_identity(admin):
    dsn = _url(ADMIN_URL, DB, "isobath_batch", "test")
    with psycopg.connect(dsn) as conn:
        for sql in (
            "select email from auth.users",
            "select pseudo_id from app.profiles",
            "delete from app.answers",
        ):
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                conn.execute(sql)
            conn.rollback()


def test_item_loader(admin):
    from isobath import items

    row = {"id": "500", "code": "X1", "item_set_version": "9.9", "kind": "quality",
           "status": "candidate", "quality_rule": '{"type":"attention","expect":4}',
           "text_ja": "q", "screening": "normal"}  # fmt: skip
    dsn = _url(ADMIN_URL, DB, "isobath_batch", "test")
    with psycopg.connect(dsn, row_factory=psycopg.rows.dict_row) as conn:
        assert items.load(conn, [items.parse(row)])["inserted"] == 1
        assert items.load(conn, [items.parse(row)])["unchanged"] == 1
        assert items.load(conn, [items.parse({**row, "status": "retired"})])["updated"] == 1
        with pytest.raises(ValueError, match=r"500\.text_ja"):
            items.load(conn, [items.parse({**row, "text_ja": "reworded"})])
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute("delete from app.questions where id = 500")
        conn.rollback()
    with pytest.raises(ValueError, match="caution needs a note"):
        items.parse({**row, "screening": "caution"})
    admin.execute("delete from app.questions where id = 500")
