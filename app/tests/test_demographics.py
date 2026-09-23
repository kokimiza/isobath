"""statistics.md §12.1: research-only covariates, dates and cut regression."""

from datetime import date, datetime

import numpy as np
import pytest
from test_statistics_sampler import small_data

from pipeline.demographics import Regression, age_at, covariates, reference_date, report
from pipeline.export import build_model
from pipeline.sampler import SamplerConfig, sample


@pytest.mark.parametrize(
    ("instant", "expected"),
    [
        ("2026-01-01T00:00:00+09:00", date(2025, 12, 31)),
        ("2024-03-10T12:00:00+09:00", date(2024, 2, 29)),
        ("2026-08-31T15:00:00+00:00", date(2026, 8, 31)),
        ("2026-08-31T14:59:59+00:00", date(2026, 7, 31)),
    ],
)
def test_previous_month_end_uses_japan_time(instant, expected):
    assert reference_date(datetime.fromisoformat(instant)) == expected


def test_age_needs_no_birth_day():
    assert age_at(2000, 8, date(2026, 8, 31)) == 26
    assert age_at(2000, 9, date(2026, 8, 31)) == 25
    assert age_at(2000, 2, date(2024, 2, 29)) == 24
    with pytest.raises(ValueError, match="later"):
        age_at(2026, 9, date(2026, 8, 31))
    with pytest.raises(ValueError, match="invalid"):
        age_at(2000, 13, date(2026, 8, 31))
    with pytest.raises(ValueError, match="integers"):
        age_at(True, 2, date(2026, 8, 31))
    with pytest.raises(ValueError, match="time zone"):
        reference_date(datetime(2026, 9, 1))  # noqa: DTZ001 - rejected input


def test_design_aligns_people_filters_consent_and_never_infers_gender():
    rows = [
        {"pseudo_id": uid, "birth_year": 2000, "birth_month": 8, "gender": gender}
        for uid, gender in [
            ("a", "female"),
            ("b", "male"),
            ("c", "neither"),
            ("d", "prefer_not_to_say"),
            ("revoked", "female"),
        ]
    ]
    x = covariates(
        ["c", "a", "b", "d", "old", "revoked"], rows, {"a", "b", "c", "d"}, date(2026, 8, 31)
    )
    np.testing.assert_allclose(x[:3], [[1, -2.4, 0, 1], [1, -2.4, 0, 0], [1, -2.4, 1, 0]])
    assert np.isnan(x[3:]).all()
    rows[0]["gender"] = "guessed"
    with pytest.raises(ValueError, match="gender"):
        covariates(["a"], rows, {"a"}, date(2026, 8, 31))


def test_conjugate_regression_draws_match_analytic_moments():
    x = np.array([[1, -1, 0, 0], [1, 0, 1, 0], [1, 1, 0, 1], [1, 2, 0, 0]])
    y = np.array([[1], [2], [4], [5]])
    regression = Regression(x)
    precision = np.diag([0.01, 1, 1, 1]) + x.T @ x
    expected = np.linalg.solve(precision, x.T @ y)
    rate = (
        1
        + (
            (y - x @ expected).T @ (y - x @ expected)
            + expected.T @ np.diag([0.01, 1, 1, 1]) @ expected
        ).item()
        / 2
    )
    rng = np.random.default_rng(52)
    draws = np.array([regression.draw(y, rng) for _ in range(12000)])[:, :, 0]
    np.testing.assert_allclose(draws.mean(0), expected[:, 0], atol=0.035)
    np.testing.assert_allclose(
        draws.var(0), np.diag(np.linalg.inv(precision)) * rate / 3, rtol=0.08
    )


def test_all_missing_and_rank_deficient_inputs_are_explicit():
    assert Regression(np.full((2, 4), np.nan)).count == 0
    reg = Regression(np.array([[1, 0, 0, 0]]))
    assert reg.rank == 1
    assert np.isfinite(reg.draw(np.ones((1, 2)), np.random.default_rng(1))).all()


def test_auxiliary_regression_does_not_change_main_sampler(tmp_path):
    data = small_data()
    config = SamplerConfig(warmup=2, draws=4, chains=2, seed=17)
    plain = sample(data, config, tmp_path / "plain")
    data.research_covariates = np.array([[1.0, 0.0, 0.0, 0.0]])
    data.age_reference_date = "2026-08-31"
    extra = sample(data, config, tmp_path / "extra")
    np.testing.assert_array_equal(plain.coordinates, extra.coordinates)
    np.testing.assert_array_equal(plain.monitor["loadings"], extra.monitor["loadings"])
    assert extra.demographic_draws.shape == (2, 4, 4, data.dimension)
    assert np.isfinite(extra.demographic_draws).all()
    plain_model = build_model(data, plain, version="test", seed=17, commit="test")
    extra_model = build_model(data, extra, version="test", seed=17, commit="test")
    assert plain_model.arrays.keys() == extra_model.arrays.keys()
    for key in plain_model.arrays:
        np.testing.assert_array_equal(plain_model.arrays[key], extra_model.arrays[key])
    summary = report(data, extra)
    assert summary["public"] is False
    assert summary["rank_deficient"]
    assert summary["age_reference_date"] == "2026-08-31"
    data.research_covariates[:] = np.nan
    assert report(data, extra)["status"] == "no_complete_cases"
    assert "mean" not in report(data, extra)
