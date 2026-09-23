from fastapi import APIRouter, Depends, Response

from ..config import CONSENT_VERSIONS, REQUIRED_CONSENTS
from ..db import user_tx
from ..errors import api_error
from ..ratelimit import limit
from ..schemas import ConsentsIn, RegistrationIn, ResearchParticipation

router = APIRouter(prefix="/v1/me")


def consent_status(conn) -> dict:
    """Current consent state from the append-only event log (app.consent_state)."""
    state = {
        r["document"]: r
        for r in conn.execute("select document, version, granted from app.consent_state")
    }

    def current(doc: str) -> bool:
        s = state.get(doc)
        return bool(s and s["granted"] and s["version"] == CONSENT_VERSIONS[doc])

    pending = conn.execute("select app.registration_required() as pending").fetchone()["pending"]
    return {
        "required": {d: CONSENT_VERSIONS[d] for d in REQUIRED_CONSENTS},
        "versions": CONSENT_VERSIONS,
        "complete": all(current(d) for d in REQUIRED_CONSENTS) and not pending,
        "registration_required": pending,
        "research": current("research"),
    }


def _record(conn, uid: str, events: list[tuple[str, str, str]]) -> None:
    with conn.cursor() as cur:
        cur.executemany(
            """insert into app.consent_events (user_id, document, version, action)
               values (%s, %s, %s, %s)""",
            [(uid, doc, version, action) for doc, version, action in events],
        )


@router.get("/consents")
def consents(claims: dict = Depends(limit("position"))):
    with user_tx(claims) as conn:
        return consent_status(conn)


@router.post("/consents", status_code=204)
def agree(body: ConsentsIn, claims: dict = Depends(limit("account"))):
    for c in body.consents:
        if CONSENT_VERSIONS.get(c.document) != c.version:
            raise api_error(422, "unknown_consent_version")
    with user_tx(claims) as conn:
        status = consent_status(conn)
        if status["registration_required"]:
            raise api_error(409, "registration_required")
        # skip no-op grants so the history only records real changes
        new = [
            (c.document, c.version, "grant")
            for c in body.consents
            if not (c.document == "research" and status["research"])
            and not (c.document in REQUIRED_CONSENTS and status["complete"])
        ]
        if new:
            _record(conn, claims["sub"], new)
    return Response(status_code=204)


@router.post("/registration", status_code=204)
def complete_registration(body: RegistrationIn, claims: dict = Depends(limit("account"))):
    versions = {c.document: c.version for c in body.consents}
    if any(versions.get(d) != CONSENT_VERSIONS[d] for d in REQUIRED_CONSENTS) or any(
        CONSENT_VERSIONS.get(d) != version for d, version in versions.items()
    ):
        raise api_error(422, "unknown_consent_version")
    with user_tx(claims) as conn:
        completed = conn.execute(
            "select app.complete_registration(%s,%s,%s) as completed",
            (body.birth_year, body.birth_month, body.gender),
        ).fetchone()["completed"]
        if not completed:
            raise api_error(409, "registration_already_completed")
        _record(conn, claims["sub"], [(doc, v, "grant") for doc, v in versions.items()])
    return Response(status_code=204)


@router.put("/research", status_code=204)
def research(body: ResearchParticipation, claims: dict = Depends(limit("account"))):
    """Join or withdraw from research use without deleting the account."""
    with user_tx(claims) as conn:
        status = consent_status(conn)
        if body.participating and status["registration_required"]:
            raise api_error(409, "registration_required")
        if status["research"] != body.participating:
            action = "grant" if body.participating else "withdraw"
            _record(conn, claims["sub"], [("research", CONSENT_VERSIONS["research"], action)])
    return Response(status_code=204)


@router.delete("", status_code=204)
def delete_me(claims: dict = Depends(limit("account"))):
    with user_tx(claims) as conn:
        conn.execute("select app.delete_me()")
    return Response(status_code=204)
