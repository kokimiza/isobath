"""statistics.md §§9.4, 10: replicated ordinal categories retain the missingness mask."""

import numpy as np
from test_statistics_sampler import small_data

from pipeline.export import build_model
from pipeline.reporting import posterior_predictive_report
from pipeline.sampler import SamplerConfig, sample


def test_posterior_predictive_report_never_counts_missing_as_category(tmp_path):
    data = small_data(3)
    result = sample(data, SamplerConfig(warmup=3, draws=5, chains=2), tmp_path)
    model = build_model(data, result, version="ppc", seed=0, commit="test")
    report = posterior_predictive_report(data, model, np.random.default_rng(3))
    assert report["observed_counts"][2] == [0] * 5
    assert report["coanswer_counts"][0][2] == 0
    assert np.array(report["observed_counts"]).sum() == np.count_nonzero(data.answers)


def test_quality_strata_and_comparison_are_reports_only(tmp_path):
    data = small_data(3)
    data.quality_scores = np.array([0.5, 0.8, 1.0])
    data.comparison_answers = {99: np.array([1.0, 3.0, 5.0])}
    result = sample(data, SamplerConfig(warmup=3, draws=5, chains=2), tmp_path)
    model = build_model(data, result, version="quality", seed=0, commit="test")
    report = posterior_predictive_report(
        data, model, np.random.default_rng(3), latent=result.raw_latent_mean
    )
    assert sum(v["people"] for v in report["quality_strata"]) == 3
    assert report["comparison_scales"][0]["question_id"] == 99
    assert 99 not in model.question_ids
