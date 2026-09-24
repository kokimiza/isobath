import json
import logging
import random
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Response
from psycopg import errors

from ..config import ITEM_SET_VERSION, get_settings
from ..cycle import current_cutoff, iso, next_cutoff
from ..db import user_tx
from ..errors import api_error
from ..ratelimit import limit
from ..schemas import AnswersIn, SessionCreate
from ..survey import assign, quality
from .account import consent_status

router = APIRouter(prefix="/v1/me/surveys")
log = logging.getLogger("isobath.surveys")

PAGE = 20


def _require_writes(initial: bool = False):
    s = get_settings()
    if not s.writes_enabled or (initial and not s.signup_enabled):
        raise api_error(503, "writes_disabled", "測深の受付を一時停止しています")


def _summary(conn, session_id) -> dict:
    return conn.execute(
        """select s.id, s.kind, s.status,
                  (select count(*) from app.survey_session_questions q where q.session_id = s.id) total,
                  (select count(*) from app.answers a where a.session_id = s.id) answered
           from app.survey_sessions s where s.id = %s""",
        (session_id,),
    ).fetchone()


def _open_session(conn) -> dict | None:
    return conn.execute("select id from app.survey_sessions where status = 'open'").fetchone()


@router.post("", status_code=201)
def create(body: SessionCreate, response: Response, claims: dict = Depends(limit("survey_create"))):
    _require_writes(initial=body.kind == "initial")
    uid = claims["sub"]
    with user_tx(claims) as conn:
        if not consent_status(conn)["complete"]:
            raise api_error(403, "consent_required")

        if (open_ := _open_session(conn)) is not None:
            response.status_code = 200
            return _summary(conn, open_["id"])

        sessions = conn.execute(
            "select kind, status, blocks, completed_at from app.survey_sessions"
        ).fetchall()
        initial_done = any(s["kind"] == "initial" and s["status"] == "completed" for s in sessions)
        now = datetime.now(UTC)
        questions = conn.execute(
            """select id, kind, anchor, block_no from app.questions
               where item_set_version = %s and status <> 'retired' and kind <> 'comparison'
               order by id""",
            (ITEM_SET_VERSION,),
        ).fetchall()
        rng = random.Random()

        if body.kind == "initial":
            if any(s["kind"] == "initial" and s["status"] != "abandoned" for s in sessions):
                raise api_error(409, "initial_exists")
            try:
                a = assign.initial(questions, rng)
            except assign.ItemBankNotReadyError as exc:
                log.error("Item set %s is not ready: %s", ITEM_SET_VERSION, exc)
                raise api_error(503, "survey_not_ready", "初回測深の質問を準備しています") from None
        else:
            if not initial_done:
                raise api_error(409, "initial_required")
            # one continuous survey per nightly window (FR-CON-05)
            if any(
                s["completed_at"] and s["completed_at"] >= current_cutoff(now) for s in sessions
            ):
                raise api_error(429, "too_soon", iso(next_cutoff(now)))
            last_answered = {
                r["question_id"]: r["answered_at"]
                for r in conn.execute("select question_id, answered_at from app.latest_answers")
            }
            seen = {b for s in sessions for b in s["blocks"]}
            a = assign.continuous(questions, last_answered, seen, now, rng)
            if not a.items:
                raise api_error(409, "nothing_to_ask")

        sid = conn.execute(
            """insert into app.survey_sessions
                 (user_id, kind, item_set_version, phase, assignment_rule, blocks)
               values (%s, %s, %s, 1, %s, %s) returning id""",
            (uid, body.kind, ITEM_SET_VERSION, a.rule, a.blocks),
        ).fetchone()["id"]
        with conn.cursor() as cur:
            cur.executemany(
                """insert into app.survey_session_questions
                     (session_id, user_id, question_id, seq, purpose, selection_prob)
                   values (%s, %s, %s, %s, %s, %s)""",
                [(sid, uid, q, i, purpose, p) for i, (q, purpose, p) in enumerate(a.items)],
            )
        return _summary(conn, sid)


@router.get("/current")
def current(claims: dict = Depends(limit("survey_read"))):
    with user_tx(claims) as conn:
        open_ = _open_session(conn)
        if open_ is None:
            raise api_error(404, "no_open_session")
        summary = _summary(conn, open_["id"])
        summary["questions"] = conn.execute(
            """select q.id, q.text_ja as text
               from app.survey_session_questions sq
               join app.questions q on q.id = sq.question_id
               where sq.session_id = %s
                 and not exists (select 1 from app.answers a
                                 where a.session_id = sq.session_id and a.question_id = sq.question_id)
               order by sq.seq limit %s""",
            (open_["id"], PAGE),
        ).fetchall()
        return summary


def _owned_open(conn, session_id: uuid.UUID) -> None:
    row = conn.execute(
        "select status from app.survey_sessions where id = %s", (session_id,)
    ).fetchone()
    if row is None:  # RLS hides other users' sessions
        raise api_error(404, "session_not_found")
    if row["status"] != "open":
        raise api_error(409, "session_closed")


@router.post("/{session_id}/answers", status_code=204)
def answers(session_id: uuid.UUID, body: AnswersIn, claims: dict = Depends(limit("answers"))):
    _require_writes()
    if len({a.question_id for a in body.answers}) != len(body.answers):
        raise api_error(422, "duplicate_question")
    try:
        with user_tx(claims) as conn:
            _owned_open(conn, session_id)
            with conn.cursor() as cur:
                cur.executemany(
                    """insert into app.answers (session_id, user_id, question_id, value, response_ms)
                       values (%s, %s, %s, %s, %s)""",
                    [
                        (session_id, claims["sub"], a.question_id, a.value, a.response_ms)
                        for a in body.answers
                    ],
                )
    except errors.ForeignKeyViolation:
        raise api_error(422, "question_not_assigned") from None
    except errors.UniqueViolation:
        raise api_error(409, "already_answered") from None
    return Response(status_code=204)


@router.post("/{session_id}/complete")
def complete(session_id: uuid.UUID, claims: dict = Depends(limit("survey_create"))):
    """Record completion time only. Positions and the chart are updated by the nightly batch,
    and completed_at decides which nightly window the session belongs to (FR-BAT-01, FR-BAT-03)."""
    _require_writes()
    uid = claims["sub"]
    with user_tx(claims) as conn:
        session = conn.execute(
            "select status, completed_at from app.survey_sessions where id = %s for update",
            (session_id,),
        ).fetchone()
        if session is None:  # Keep the same RLS ownership boundary on retries.
            raise api_error(404, "session_not_found")
        if session["status"] == "completed":
            return {
                "session_id": str(session_id),
                "next_update_at": iso(next_cutoff(session["completed_at"])),
            }
        if session["status"] != "open":
            raise api_error(409, "session_closed")
        rows = conn.execute(
            """select sq.question_id, q.code, sq.purpose, q.quality_rule, a.value, a.response_ms
                   from app.survey_session_questions sq
                   join app.questions q on q.id = sq.question_id
                   left join app.answers a
                     on a.session_id = sq.session_id and a.question_id = sq.question_id
                   where sq.session_id = %s""",
            (session_id,),
        ).fetchall()
        if any(r["value"] is None for r in rows):
            raise api_error(409, "unanswered_questions")

        completed_at = conn.execute(
            "update app.survey_sessions set status = 'completed', completed_at = now() where id = %s "
            "returning completed_at",
            (session_id,),
        ).fetchone()["completed_at"]
        flags, data_quality_score = quality.compute(rows)
        conn.execute(
            """insert into app.quality_flags (session_id, user_id, flags, data_quality_score)
                   values (%s, %s, %s::jsonb, %s)""",
            (session_id, uid, _json(flags), data_quality_score),
        )

        return {
            "session_id": str(session_id),
            "next_update_at": iso(next_cutoff(completed_at)),
        }


def _json(v) -> str | None:
    return None if v is None else json.dumps(v)
