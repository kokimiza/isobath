"""Prior/SBC/recovery and respondent-held-out research utilities (§§0, 9)."""

from dataclasses import replace

import numpy as np
from scipy.special import logsumexp, ndtri

from isobath.inference.ordinal import interval_log_probability

from .data import Dataset
from .niw import NIW
from .partitions import canonical
from .sampler import measurement_priors


def respondent_split(n, rng):
    if n < 6:
        raise ValueError("three independent respondent sets require at least six people")
    indices = rng.permutation(n)
    return tuple(np.array_split(indices, 3))


def subset(data, indices):
    return replace(
        data,
        answers=data.answers[indices].copy(),
        user_ids=[data.user_ids[i] for i in indices],
        quality_scores=data.quality_scores[indices] if data.quality_scores is not None else None,
        comparison_answers={q: v[indices] for q, v in data.comparison_answers.items()},
        research_covariates=data.research_covariates[indices].copy()
        if data.research_covariates is not None
        else None,
    )


def simulate_prior(
    n, items, dimension, rng, *, components=None, separation=0.0, missing=0.3, condition="normal"
):
    if n < 1 or items < dimension:
        raise ValueError("invalid simulation dimensions")
    domains = np.arange(items) % dimension
    data = Dataset(
        np.zeros((n, items), dtype=int),
        list(range(1, items + 1)),
        [f"sim-{i}" for i in range(n)],
        domains,
        np.where(np.arange(items) % 2, -1, 1),
        np.arange(items) < dimension,
        "simulation",
        dimension,
    )
    mean, variance = measurement_priors(data)
    loadings = rng.normal(mean, np.sqrt(variance))
    for j in range(dimension):
        while data.signs[j] * loadings[j, j] <= 0:
            loadings[j, j] = rng.normal(mean[j, j], np.sqrt(variance[j, j]))
    tau = np.empty((items, 4))
    for j in range(items):
        # Sorting independent unequal-mean normals would change the specified prior.
        while True:
            trial = rng.normal(ndtri(np.arange(1, 5) / 5), 1.0)
            if np.all(np.diff(trial) > 0):
                tau[j] = trial
                break
    k = int(1 + rng.poisson(1)) if components is None else components
    weights = rng.dirichlet(np.ones(k))
    prior = NIW.default(dimension)
    parameters = [prior.sample(rng) for _ in range(k)]
    means, sigma = np.array([p[0] for p in parameters]), np.array([p[1] for p in parameters])
    if components is not None:
        weights = np.full(k, 1 / k)
        means[:] = 0
        means[:, 0] = separation * (np.arange(k) - (k - 1) / 2)
        sigma[:] = np.eye(dimension) * 0.5
    z = rng.choice(k, n, p=weights)
    f = np.array([rng.multivariate_normal(means[c], sigma[c]) for c in z])
    if condition == "heavy_tail":
        f /= np.sqrt(rng.chisquare(3, n) / 3)[:, None]
    elif condition == "skew":
        f[:, 0] = np.exp(f[:, 0]) - np.exp(0.25)
    residual = rng.normal(size=(n, items))
    if condition == "local_dependence" and items >= 2:
        residual[:, 1] = 0.7 * residual[:, 0] + np.sqrt(1 - 0.7**2) * residual[:, 1]
    ystar = f @ loadings.T + residual
    y = 1 + np.sum(ystar[:, :, None] > tau[None, :, :], axis=2)
    if condition == "careless":
        careless = rng.random(n) < 0.1
        y[careless] = rng.integers(1, 6, size=(careless.sum(), 1))
    y[rng.random(y.shape) < missing] = 0
    data.answers = y
    data.validate()
    return data, {
        "tau": tau,
        "loadings": loadings,
        "f_probe": f[: min(n, 4)],
        "f": f,
        "z": canonical(z),
        "K": k,
        "w": weights,
        "m": means,
        "Sigma": sigma,
    }


def predictive_density(model, answers, rng, samples=1024):
    a = model.arrays
    idx = np.array([model.index[q] for q in sorted(answers) if q in model.index], dtype=int)
    values = np.array([answers[q] for q in sorted(answers) if q in model.index], dtype=int)
    logs = []
    for s, weights in enumerate(a["draws_w"]):
        z = rng.choice(len(weights), samples, p=weights)
        f = np.array(
            [rng.multivariate_normal(a["draws_m"][s, c], a["draws_Sigma"][s, c]) for c in z]
        )
        if "draws_nu" in a:
            nu = a["draws_nu"][s]
            f = (
                a["draws_m"][s, z]
                + (f - a["draws_m"][s, z]) / np.sqrt(rng.chisquare(nu, samples) / nu)[:, None]
            )
        if len(idx):
            bounds = np.column_stack(
                [np.full(len(idx), -np.inf), a["draws_tau"][s, idx], np.full(len(idx), np.inf)]
            )
            eta = f @ a["draws_Lambda"][s, idx].T
            log_likelihood = interval_log_probability(
                bounds[np.arange(len(idx)), values - 1] - eta,
                bounds[np.arange(len(idx)), values] - eta,
            ).sum(axis=1)
        else:
            log_likelihood = np.zeros(samples)
        logs.append(log_likelihood)
    logs = np.array(logs)
    value = float(logsumexp(logs) - np.log(logs.size))
    # Inner integration error, separate from posterior MCMC error.
    shifted = np.exp(logs - value)
    error = float(np.sqrt(np.var(shifted, axis=1, ddof=1).sum() / samples) / len(logs))
    return {
        "log_density": value,
        "integration_mcse": error,
        "samples_per_draw": samples,
        "importance_ess": float(shifted.sum() ** 2 / np.sum(shifted**2)),
    }


def stability_decision(comparisons):
    if len(comparisons) < 2:
        return False
    return all(
        r["tv_upper"] <= 0.10
        and r["profile_upper"] <= 0.20
        and r["unmatched_upper"] <= 0.05
        and r["predictive_change_upper"] <= 0.05
        and r["normal_gain_lower"] > 0
        and r["student_gain_lower"] > 0
        and r["independent_replication"]
        and r["has_regions"]
        for r in comparisons[-2:]
    )
