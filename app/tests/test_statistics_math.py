"""Executable contracts for statistics.md §§2.2, 3, 4.2, 5, 6.1 (not recovery claims)."""

import itertools
import math

import numpy as np
import pytest
from scipy.special import logsumexp
from scipy.stats import multivariate_t

from pipeline.coordinates import projection, standardize
from pipeline.mfm import MFM
from pipeline.niw import NIW
from pipeline.partitions import canonical, log_target, split_merge, vi


def partitions(n):
    for z in itertools.product(range(n), repeat=n):
        if tuple(canonical(np.array(z))) == z:
            yield np.array(z)


def test_mfm_prior_normalizes_over_all_small_partitions():
    mfm = MFM()
    for n in range(1, 6):
        assert sum(np.exp(mfm.log_partition(z)) for z in partitions(n)) == pytest.approx(1)
    assert np.exp(mfm.log_partition(np.array([0, 0]))) == pytest.approx(0.7357588823)


def test_series_extends_beyond_initial_limit_and_certifies_error():
    mfm = MFM(initial_limit=2)
    result = mfm.series(120, 30)
    assert result.support[0] == 30
    assert result.support[-1] > 30
    assert result.relative_error <= 1e-10
    larger = MFM(initial_limit=200, tolerance=1e-12)
    assert mfm.log_v(120, 30) == pytest.approx(larger.log_v(120, 30), abs=1e-9)
    assert mfm.log_ratio(120, 30) == pytest.approx(larger.log_ratio(120, 30), abs=1e-8)


def test_k_restoration_keeps_unseen_mass():
    mfm = MFM()
    result = mfm.series(1, 1)
    assert result.probabilities.sum() == pytest.approx(1)
    # A single person's occupancy is certain, but K is exactly its prior.
    assert result.probabilities[0] == pytest.approx(math.exp(-1))
    rng = np.random.default_rng(781)
    masses = []
    for _ in range(6000):
        k, w = mfm.restore(np.array([1]), rng)
        assert k >= 1
        assert len(w) == k
        masses.append(w[1:].sum())
    assert np.mean(masses) == pytest.approx(1 - 0.7357588823, abs=0.015)


def test_niw_predictive_equals_marginal_likelihood_ratio():
    prior = NIW.default(3)
    rng = np.random.default_rng(2)
    data = rng.normal(size=(8, 3))
    point = np.array([0.4, -0.2, 1.3])
    post = prior.posterior(data)
    df = post.nu - 3 + 1
    expected = multivariate_t.logpdf(
        point, loc=post.mean, shape=post.psi * (post.kappa + 1) / (post.kappa * df), df=df
    )
    assert prior.log_predictive(point, data) == pytest.approx(expected)
    assert prior.log_marginal(np.vstack([data, point])) - prior.log_marginal(data) == pytest.approx(
        expected
    )


def test_split_merge_stationarity_against_exact_enumeration():
    # §4.1: checks the global move alone, so local Gibbs cannot hide a wrong MH ratio.
    x = np.array([[-0.6], [0.2], [0.7]])
    prior, mfm = NIW.default(1), MFM()
    states = list(partitions(3))
    target = np.array([log_target(x, z, prior, mfm) for z in states])
    target = np.exp(target - logsumexp(target))
    counts = dict.fromkeys([tuple(z) for z in states], 0)
    rng, z = np.random.default_rng(211), np.zeros(3, dtype=int)
    for step in range(8000):
        z, _ = split_merge(x, z, prior, mfm, rng)
        if step >= 1000:
            counts[tuple(z)] += 1
    observed = np.array(list(counts.values())) / 7000
    assert np.abs(observed - target).max() < 0.045


def test_vi_is_label_invariant_and_singleton_is_zero():
    assert vi(np.array([2, 2, 7]), np.array([0, 0, 1])) == pytest.approx(0)
    assert vi(np.zeros(3, dtype=int), np.arange(3)) == pytest.approx(np.log(3))
    assert vi(np.array([0]), np.array([99]), normalized=True) == 0


def test_standardization_preserves_ordinal_predictors_including_empty_components():
    weights = np.array([0.6, 0.4])
    means = np.array([[1.0, 0.0, 0.0, 0.0], [-2.0, 0.0, 0.0, 0.0]])
    covs = np.stack([np.eye(4), 2 * np.eye(4)])
    loadings, tau = np.ones((2, 4)), np.tile([-1.0, 0.0, 1.0, 2.0], (2, 1))
    f = np.array([[1.0, 2.0, 3.0, 4.0]])
    out = standardize(weights, means, covs, loadings, tau, f)
    assert np.allclose(tau - (f @ loadings.T).T, out["tau"] - (out["f"] @ out["Lambda"].T).T)
    assert np.allclose(weights @ out["m"], 0)
    assert np.allclose(projection(16) @ projection(16).T, np.eye(2))
    assert np.flatnonzero(projection(16)[1]).tolist() == [3]
