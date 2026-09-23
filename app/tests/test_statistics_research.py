"""statistics.md §§0, 9: independent respondents, predictive integration, SBC."""

import numpy as np
import pytest

from pipeline.data import from_records
from pipeline.research import (
    predictive_density,
    respondent_split,
    simulate_prior,
    stability_decision,
)


def test_holdout_is_by_person_with_no_overlap():
    parts = respondent_split(40, np.random.default_rng(1))
    assert len(set(parts[0]) & set(parts[1])) == 0
    assert len(set(parts[0]) & set(parts[2])) == 0
    assert len(set(parts[1]) & set(parts[2])) == 0
    assert sum(map(len, parts)) == 40


def test_predictive_density_integrates_new_person_not_fitted_score(model):
    result = predictive_density(model, {1: 5}, np.random.default_rng(1), samples=4000)
    assert np.isfinite(result["log_density"])
    assert result["log_density"] < 0
    empty = predictive_density(model, {}, np.random.default_rng(1), samples=4)
    assert empty["log_density"] == pytest.approx(0)


def test_prior_simulation_returns_ordered_answers_and_one_sign_anchor():
    data, truth = simulate_prior(12, 8, 2, np.random.default_rng(92))
    data.validate()
    assert np.isin(data.answers, range(6)).all()
    assert np.all(np.diff(truth["tau"], axis=1) > 0)
    assert len(truth["z"]) == 12


def test_stability_requires_independent_replication_and_both_baselines():
    record = {
        "tv_upper": 0.05,
        "profile_upper": 0.1,
        "unmatched_upper": 0.02,
        "predictive_change_upper": 0.03,
        "normal_gain_lower": 0.1,
        "student_gain_lower": 0.1,
        "independent_replication": True,
        "has_regions": True,
    }
    assert stability_decision([record, record])
    assert not stability_decision([{**record, "student_gain_lower": -0.01}, record])
    assert not stability_decision([{**record, "independent_replication": False}, record])


def test_extraction_filters_consent_tombstones_version_kind_and_latest():
    questions = [
        {
            "id": i + 1,
            "kind": "personality",
            "domain": f"D{i + 1:02d}",
            "keyed": 1,
            "item_set_version": "v",
        }
        for i in range(16)
    ]
    responses = [
        {
            "pseudo_id": uid,
            "question_id": 1,
            "value": v,
            "answered_at": f"2026-09-23T00:00:0{v}+00:00",
            "session_id": str(v),
            "item_set_version": "v",
        }
        for uid in ("ok", "no", "deleted")
        for v in (2, 4)
    ]
    data = from_records(
        responses, questions, {"ok", "deleted"}, {"deleted"}, "v", set(range(1, 17))
    )
    assert data.user_ids == ["ok"]
    assert data.answers[0, 0] == 4
    assert data.answers[0, 1] == 0


def test_latest_answer_uses_instant_not_iso_text_order():
    questions = [
        {
            "id": i + 1,
            "kind": "personality",
            "domain": f"D{i + 1:02d}",
            "keyed": 1,
            "item_set_version": "v",
        }
        for i in range(16)
    ]
    responses = [
        {
            "pseudo_id": "ok",
            "question_id": 1,
            "value": value,
            "answered_at": timestamp,
            "session_id": str(value),
            "item_set_version": "v",
        }
        for value, timestamp in [(1, "2026-09-23T11:00:00+09:00"), (5, "2026-09-23T03:00:00+00:00")]
    ]
    data = from_records(responses, questions, {"ok"}, set(), "v", set(range(1, 17)))
    assert data.answers[0, 0] == 5
