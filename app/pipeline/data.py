"""Consent-filtered, pseudonymous, latest-per-item research input (§§1, 10)."""

from dataclasses import dataclass, field
from datetime import datetime

import numpy as np

from .demographics import covariates, reference_date


@dataclass
class Dataset:
    answers: np.ndarray
    question_ids: list[int]
    user_ids: list[str]
    domains: np.ndarray
    signs: np.ndarray
    anchors: np.ndarray
    item_set_version: str
    dimension: int = 16
    quality_scores: np.ndarray | None = None
    comparison_answers: dict[int, np.ndarray] = field(default_factory=dict)
    research_covariates: np.ndarray | None = None
    age_reference_date: str | None = None

    def validate(self):
        n, j = self.answers.shape
        if self.research_covariates is not None and self.research_covariates.shape != (n, 4):
            raise ValueError("research covariate shape mismatch")
        if not n or not j or (n, j) != (len(self.user_ids), len(self.question_ids)):
            raise ValueError("empty or inconsistent dataset")
        if len(set(self.user_ids)) != n or len(set(self.question_ids)) != j:
            raise ValueError("duplicate identifiers")
        if not np.isin(self.answers, np.arange(6)).all():
            raise ValueError("categories must be 1..5 or 0 for missing")
        if any(len(a) != j for a in (self.domains, self.signs, self.anchors)):
            raise ValueError("item design shape mismatch")
        if (
            not np.isin(self.signs, [-1, 1]).all()
            or np.any(self.domains < 0)
            or np.any(self.domains >= self.dimension)
        ):
            raise ValueError("invalid domain or direction")
        for d in range(self.dimension):
            if np.sum(self.anchors & (self.domains == d)) != 1:
                raise ValueError("exactly one sign anchor per factor is required")


def from_records(  # noqa: PLR0917 - extraction contract
    responses,
    questions,
    participants,
    tombstones,
    version,
    sign_anchor_ids,
    min_quality=0.0,
    *,
    demographics=(),
    demographic_participants=(),
    cutoff=None,
):
    """Explicit current consent/tombstones also required when replaying a private export."""
    allowed = set(map(str, participants)) - set(map(str, tombstones))
    items = sorted(
        (q for q in questions if q["item_set_version"] == version and q["kind"] == "personality"),
        key=lambda q: q["id"],
    )
    index = {q["id"]: j for j, q in enumerate(items)}
    comparison_ids = {
        q["id"] for q in questions if q["item_set_version"] == version and q["kind"] == "comparison"
    }
    latest = {}
    timestamps = {}
    for row in responses:
        uid, qid = str(row["pseudo_id"]), row["question_id"]
        if (
            uid not in allowed
            or qid not in index.keys() | comparison_ids
            or row["item_set_version"] != version
        ):
            continue
        if row.get("data_quality_score") is not None and row["data_quality_score"] < min_quality:
            continue
        key = (uid, qid)
        instant = row["answered_at"]
        if isinstance(instant, str):
            instant = datetime.fromisoformat(instant)
        if not isinstance(instant, datetime) or instant.tzinfo is None:
            raise ValueError("answer timestamp must include a time zone")
        ordering = instant, str(row["session_id"])
        if key not in latest or ordering > timestamps[key]:
            latest[key] = row
            timestamps[key] = ordering
    users = sorted({uid for uid, qid in latest if qid in index})
    users_index = {uid: i for i, uid in enumerate(users)}
    answers = np.zeros((len(users), len(items)), dtype=np.int8)
    comparisons = {qid: np.full(len(users), np.nan) for qid in comparison_ids}
    scores = {uid: [] for uid in users}
    for (uid, qid), row in latest.items():
        value = row["value"]
        if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 5:
            raise ValueError("invalid answer category")
        if uid not in users_index:
            continue
        if qid in index:
            answers[users_index[uid], index[qid]] = value
            if row.get("data_quality_score") is not None:
                scores[uid].append(float(row["data_quality_score"]))
        else:
            comparisons[qid][users_index[uid]] = value
    data = Dataset(
        answers,
        list(index),
        users,
        np.array([int(q["domain"][1:]) - 1 for q in items]),
        np.array([q["keyed"] for q in items]),
        np.array([q["id"] in sign_anchor_ids for q in items]),
        version,
    )
    data.quality_scores = np.array(
        [np.mean(scores[uid]) if scores[uid] else np.nan for uid in users]
    )
    data.comparison_answers = comparisons
    if cutoff is not None:
        reference = reference_date(cutoff)
        data.age_reference_date = reference.isoformat()
        data.research_covariates = covariates(
            users, demographics, demographic_participants, reference
        )
    data.validate()
    return data


def extract(conn, version, sign_anchor_ids, cutoff, min_quality=0.0):
    conn.execute("set transaction isolation level repeatable read read only")
    responses = conn.execute(
        "select * from analysis.responses where item_set_version = %s and completed_at < %s",
        (version, cutoff),
    ).fetchall()
    questions = conn.execute(
        "select * from analysis.questions where item_set_version = %s", (version,)
    ).fetchall()
    participants = [
        r["pseudo_id"] for r in conn.execute("select pseudo_id from analysis.research_participants")
    ]
    tombstones = [r["pseudo_id"] for r in conn.execute("select pseudo_id from analysis.tombstones")]
    demographics = conn.execute("select * from analysis.research_demographics").fetchall()
    return from_records(
        responses,
        questions,
        participants,
        tombstones,
        version,
        sign_anchor_ids,
        min_quality,
        demographics=demographics,
        demographic_participants=[r["pseudo_id"] for r in demographics],
        cutoff=cutoff,
    )
