"""statistics.md §§4.3, 6, 7, 9: diagnostics, publication gates and validation metrics."""

import numpy as np
import pytest
from test_statistics_sampler import small_data

from isobath.inference.regions import ellipse
from pipeline.diagnostics import diagnose, require_convergence
from pipeline.export import build_model
from pipeline.sampler import SamplerConfig, sample
from pipeline.validation import calibration_summary, membership_calibration, wilson_interval


def test_convergence_checks_constants_without_masking_disagreeing_chains():
    rng = np.random.default_rng(14)
    good = diagnose({"x": rng.normal(size=(4, 1000)), "T_N": np.ones((4, 1000))})
    require_convergence(good)
    bad = diagnose({"x": np.tile(np.arange(4)[:, None], (1, 1000))})
    with pytest.raises(ValueError, match="convergence"):
        require_convergence(bad)


def test_wilson_and_calibration_report_uncertainty_instead_of_boolean_per_draw():
    low, high = wilson_interval(950, 1000)
    assert 0.93 < low < 0.95 < high < 0.97
    summary = calibration_summary([True] * 19 + [False])
    assert summary["standard_error"] == pytest.approx(np.sqrt(0.95 * 0.05 / 20))
    assert not summary["accepted"]


def test_empirical_ellipse_covers_skewed_heavy_tailed_draws():
    rng = np.random.default_rng(2)
    x = np.column_stack([rng.lognormal(size=2000), rng.standard_t(3, 2000)])
    result = ellipse(x)
    assert 0.95 <= result["mass"] < 0.952


def test_membership_calibration_is_invariant_to_component_labels():
    truth = np.array([0, 0, 1, 1])
    report = membership_calibration(np.array([[8, 8, 4, 4], [2, 2, 9, 9]]), truth)
    assert report["brier_score"] == 0


def test_sampler_export_preserves_variable_k_and_label_mapping(tmp_path):
    data = small_data()
    result = sample(data, SamplerConfig(warmup=4, draws=8, chains=2), tmp_path)
    model = build_model(data, result, version="smoke", seed=0, commit="test", saved_draws=12)
    a = model.arrays
    assert np.all(a["draws_T"] == 1)
    assert np.any(a["draws_K"] > 1)
    assert np.all(a["draws_component_to_region"][a["draws_valid"] & ~a["draws_occupied"]] == -2)
    assert np.allclose(a["draws_w"].sum(axis=1), 1)
    assert model.meta["n_observers"] == 1
    assert not model.has_regions
