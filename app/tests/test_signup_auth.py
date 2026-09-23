"""Real GoTrue integration; point ONLY at a disposable, migrated Auth/DB pair.

ISOBATH_AUTH_TEST_URL and ISOBATH_AUTH_TEST_PG enable these tests. Email must be
auto-confirmed in this isolated test Auth instance. No production credentials.
"""

import os
import uuid

import httpx
import jwt
import psycopg
import pytest

AUTH_URL = os.environ.get("ISOBATH_AUTH_TEST_URL")
PG_URL = os.environ.get("ISOBATH_AUTH_TEST_PG")
pytestmark = pytest.mark.skipif(not (AUTH_URL and PG_URL), reason="isolated GoTrue not configured")


def test_real_auth_creates_pending_account_without_demographics_in_jwt():
    response = httpx.post(
        f"{AUTH_URL}/signup",
        json={
            "email": f"demographics-{uuid.uuid4()}@example.com",
            "password": "Test-only-password-523!",
            "data": {},
        },
    )
    assert response.status_code == 200
    body = response.json()
    user = body["user"]
    uid = user["id"]
    with psycopg.connect(PG_URL, autocommit=True) as conn:
        try:
            assert "research_demographics" not in user["user_metadata"]
            claims = jwt.decode(body["access_token"], options={"verify_signature": False})
            assert "research_demographics" not in claims["user_metadata"]
            assert (
                conn.execute(
                    "select * from app.research_demographics where user_id=%s", (uid,)
                ).fetchone()
                is None
            )
            assert (
                conn.execute(
                    "select user_id from app.pending_registrations where user_id=%s", (uid,)
                ).fetchone()
                is not None
            )
            assert (
                conn.execute(
                    "select count(*) from auth.identities where user_id=%s and identity_data ? 'research_demographics'",
                    (uid,),
                ).fetchone()[0]
                == 0
            )
        finally:
            conn.execute("delete from auth.users where id=%s", (uid,))
