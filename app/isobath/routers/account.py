from fastapi import APIRouter, Depends, Response

from ..config import CONSENT_VERSIONS
from ..db import user_tx
from ..errors import api_error
from ..ratelimit import limit
from ..schemas import ConsentsIn

router = APIRouter(prefix="/v1/me")


@router.get("/consents")
def consents(claims: dict = Depends(limit("position"))):
    with user_tx(claims) as conn:
        rows = conn.execute("select document, version, agreed_at from app.consents").fetchall()
    agreed = {(r["document"], r["version"]) for r in rows}
    return {
        "required": CONSENT_VERSIONS,
        "complete": set(CONSENT_VERSIONS.items()) <= agreed,
        "agreed": rows,
    }


@router.post("/consents", status_code=204)
def agree(body: ConsentsIn, claims: dict = Depends(limit("account"))):
    for c in body.consents:
        if CONSENT_VERSIONS.get(c.document) != c.version:
            raise api_error(422, "unknown_consent_version")
    with user_tx(claims) as conn, conn.cursor() as cur:
        cur.executemany(
            """insert into app.consents (user_id, document, version) values (%s, %s, %s)
                   on conflict do nothing""",
            [(claims["sub"], c.document, c.version) for c in body.consents],
        )
    return Response(status_code=204)


@router.delete("", status_code=204)
def delete_me(claims: dict = Depends(limit("account"))):
    with user_tx(claims) as conn:
        conn.execute("select app.delete_me()")
    return Response(status_code=204)
