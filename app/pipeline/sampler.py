"""Partially collapsed ordinal MFM Gibbs sampler; statistics.md §4.

Parameters are sampled on the raw prior scale. Only saved draws are standardized.
Large N-dependent chains live in private memory-mapped files, not Python lists.
"""

from dataclasses import dataclass

import numpy as np
from scipy.cluster.vq import kmeans2
from scipy.special import gammaln, ndtri

from isobath.inference.ordinal import (
    interval_log_probability,
    normal_from_precision,
    truncated_normal,
)

from .coordinates import projection, standardize
from .data import loading_mask
from .demographics import Regression
from .mfm import MFM
from .niw import NIW
from .partitions import canonical, gibbs_partition, split_merge


@dataclass(frozen=True)
class SamplerConfig:
    warmup: int = 1000
    draws: int = 1000
    chains: int = 4
    seed: int = 0
    gamma: float = 1.0
    poisson_mean: float = 1.0
    series_tolerance: float = 1e-10
    series_limit: int = 16
    structure: str = "mfm"
    kappa: float = 0.1
    within_variance: float = 0.5
    main_loading_mean: float = 0.6
    main_loading_sd: float = 0.3

    def __post_init__(self):
        if self.warmup < 0 or self.draws < 2 or self.chains < 2 or self.seed < 0:
            raise ValueError("invalid sampler configuration")
        if self.structure not in ("mfm", "normal", "student"):
            raise ValueError("unknown structural model")
        if min(self.kappa, self.within_variance, self.main_loading_sd) <= 0:
            raise ValueError("prior scales must be positive")


@dataclass
class SampleResult:
    draws: list[dict]
    partitions: np.ndarray
    coordinates: np.ndarray
    occupancy: np.ndarray
    monitor: dict[str, np.ndarray]
    latent_mean: np.ndarray
    latent_cov: np.ndarray
    series: dict
    split_merge_acceptance: float
    raw_latent_mean: np.ndarray
    demographic_draws: np.ndarray | None = None


def measurement_priors(data, config=None):
    config = config or SamplerConfig()
    j, d = len(data.question_ids), data.dimension
    mean, variance = np.zeros((j, d)), np.full((j, d), 0.1**2)
    active = data.domains >= 0
    if data.spatial:
        variance[~active] = config.main_loading_sd**2
    rows, domains = np.flatnonzero(active), data.domains[active]
    mean[rows, domains] = config.main_loading_mean * data.signs[active]
    variance[rows, domains] = np.where(data.anchors[active], 0.2**2, config.main_loading_sd**2)
    return mean, variance


def update_loading(rng, precision, information, anchor, sign):
    if anchor is None:
        return normal_from_precision(rng, precision, information)
    # Sample the truncated marginal, then the conditional remaining coordinates.
    cov = np.linalg.solve(precision, np.eye(len(information)))
    mean = cov @ information
    value = sign * truncated_normal(
        rng, sign * mean[anchor], np.sqrt(cov[anchor, anchor]), 0, np.inf
    )
    rest = np.arange(len(mean)) != anchor
    result = np.empty(len(mean))
    result[anchor] = value
    result[rest] = normal_from_precision(
        rng, precision[np.ix_(rest, rest)], information[rest] - precision[rest, anchor] * value
    )
    return result


def sample(data, config, directory) -> SampleResult:
    data.validate()
    directory.mkdir(parents=True, exist_ok=True)
    n, j = data.answers.shape
    d, count = data.dimension, config.chains * config.draws
    regression = (
        Regression(data.research_covariates) if data.research_covariates is not None else None
    )
    demographic_draws = (
        np.empty((config.chains, config.draws, 4, d))
        if regression is not None and regression.count
        else None
    )
    # A separate stream prevents auxiliary research from perturbing the chart posterior.
    research_rng = np.random.default_rng(np.random.SeedSequence([config.seed, 1201]))
    partitions = np.lib.format.open_memmap(
        directory / "partitions.npy",
        mode="w+",
        dtype="int32",
        shape=(config.chains, config.draws, n),
    )
    coordinates = np.lib.format.open_memmap(
        directory / "coordinates.npy",
        mode="w+",
        dtype="float32",
        shape=(config.chains, config.draws, n, 3 if data.spatial else 2),
    )
    occupancy = np.zeros((config.chains, config.draws), dtype=int)
    monitor = {
        "tau": np.empty((config.chains, config.draws, j, 4)),
        "loadings": np.empty((config.chains, config.draws, j, d)),
        "f_probe": np.empty((config.chains, config.draws, min(n, 4), d)),
        "log_likelihood": np.empty((config.chains, config.draws)),
    }
    if config.structure == "student":
        monitor["nu"] = np.empty((config.chains, config.draws))
    mean_f, m2 = np.zeros((n, d)), np.zeros((n, d, d))
    raw_mean = np.zeros((n, d))
    prior_mean, prior_variance = measurement_priors(data, config)
    free_loadings = loading_mask(data)
    prior = NIW(np.zeros(d), config.kappa, d + 6.0, 5 * config.within_variance * np.eye(d))
    mfm = MFM(config.gamma, config.poisson_mean, config.series_tolerance, config.series_limit)
    ii, jj = np.nonzero(data.answers)
    values = data.answers[ii, jj]
    item_edges = [np.flatnonzero(jj == q) for q in range(j)]
    person_edges = [np.flatnonzero(ii == p) for p in range(n)]
    threshold_mean = ndtri(np.arange(1, 5) / 5)
    draws, accepted, moves, saved = [], 0, 0, 0
    for chain, seed in enumerate(np.random.SeedSequence(config.seed).spawn(config.chains)):
        rng = np.random.default_rng(seed)
        f = rng.normal(size=(n, d))
        nu, local_scales = 12.0, np.ones(n)
        if chain == 0 or n == 1 or config.structure != "mfm":
            z = np.zeros(n, dtype=int)
        elif chain == 1:
            _, z = kmeans2(f, min(10, n), minit="points", rng=rng)
        else:
            z = canonical(rng.integers(0, min(10, n), n))
        loadings = prior_mean.copy()
        tau = np.tile(threshold_mean, (j, 1))
        components = [prior.posterior(f[z == c]).sample(rng) for c in range(z.max() + 1)]
        for iteration in range(config.warmup + config.draws):
            bounds = np.column_stack([np.full(j, -np.inf), tau, np.full(j, np.inf)])
            ystar = truncated_normal(
                rng,
                np.sum(loadings[jj] * f[ii], axis=1),
                1.0,
                bounds[jj, values - 1],
                bounds[jj, values],
            )
            for q, edges in enumerate(item_edges):
                # Exact full conditional: an independence-MH proposal accepted with probability 1.
                for c in range(4):
                    below = ystar[edges][values[edges] <= c + 1]
                    above = ystar[edges][values[edges] > c + 1]
                    lo = max(tau[q, c - 1] if c else -np.inf, np.max(below, initial=-np.inf))
                    hi = min(tau[q, c + 1] if c < 3 else np.inf, np.min(above, initial=np.inf))
                    tau[q, c] = truncated_normal(rng, threshold_mean[c], 1.0, lo, hi)
                design = f[ii[edges]]
                precision = np.diag(1 / prior_variance[q]) + design.T @ design
                information = prior_mean[q] / prior_variance[q] + design.T @ ystar[edges]
                free = free_loadings[q]
                loadings[q, free] = update_loading(
                    rng,
                    precision[np.ix_(free, free)],
                    information[free],
                    int(data.domains[q]) if data.anchors[q] else None,
                    data.signs[q],
                )
            for i, edges in enumerate(person_edges):
                m, sigma = components[z[i]]
                inv = local_scales[i] * np.linalg.solve(sigma, np.eye(d))
                design = loadings[jj[edges]]
                f[i] = normal_from_precision(
                    rng, inv + design.T @ design, inv @ m + design.T @ ystar[edges]
                )
            accept = False
            if config.structure == "mfm":
                z = gibbs_partition(f, z, prior, mfm, rng)
                z, accept = split_merge(f, z, prior, mfm, rng)
            accepted += accept
            moves += n > 1
            t = int(z.max() + 1)
            if config.structure == "student":
                m, sigma = components[0]
                delta = f - m
                quad = np.einsum("ni,in->n", delta, np.linalg.solve(sigma, delta.T))
                local_scales = rng.gamma((nu + d) / 2, 2 / (nu + quad))
                proposal = 2 + np.exp(np.log(nu - 2) + rng.normal(0, 0.25))

                def nu_log_density(v, local_scales=local_scales):
                    a = v / 2
                    return (
                        -0.1 * (v - 2)
                        + n * (a * np.log(a) - gammaln(a))
                        + (a - 1) * np.log(local_scales).sum()
                        - a * local_scales.sum()
                        + np.log(v - 2)
                    )

                if np.log(rng.uniform()) < nu_log_density(proposal) - nu_log_density(nu):
                    nu = proposal
                weight = local_scales.sum()
                mean = np.average(f, axis=0, weights=local_scales)
                centered = f - mean
                kappa = prior.kappa + weight
                psi = (
                    prior.psi
                    + centered.T @ (centered * local_scales[:, None])
                    + prior.kappa * weight / kappa * np.outer(mean, mean)
                )
                components = [NIW(weight * mean / kappa, kappa, prior.nu + n, psi).sample(rng)]
            else:
                components = [prior.posterior(f[z == c]).sample(rng) for c in range(t)]
            if iteration < config.warmup:
                continue
            k, w = (
                mfm.restore(np.bincount(z), rng) if config.structure == "mfm" else (1, np.ones(1))
            )
            all_components = components + [prior.sample(rng) for _ in range(k - t)]
            transformed = standardize(
                w,
                np.array([v[0] for v in all_components]),
                np.array([v[1] for v in all_components]),
                loadings,
                tau,
                f,
            )
            if config.structure == "student":
                adjustment = np.sqrt(nu / (nu - 2))
                transformed["a"] *= adjustment
                transformed["f"] /= adjustment
                transformed["m"] /= adjustment
                transformed["Sigma"] /= adjustment**2
                transformed["Lambda"] *= adjustment
                transformed["nu"] = nu
            transformed.update(w=w, K=k, T=t, chain=chain, iteration=iteration)
            current_f = transformed.pop("f")
            draws.append(transformed)
            s = iteration - config.warmup
            if demographic_draws is not None:
                demographic_draws[chain, s] = regression.draw(current_f, research_rng)
            partitions[chain, s] = z
            coordinates[chain, s] = current_f @ projection(d, spatial=data.spatial).T
            occupancy[chain, s] = t
            if config.structure == "student":
                monitor["nu"][chain, s] = nu
            monitor["tau"][chain, s] = tau
            monitor["loadings"][chain, s] = loadings
            monitor["f_probe"][chain, s] = f[: min(n, 4)]
            bounds = np.column_stack([np.full(j, -np.inf), tau, np.full(j, np.inf)])
            predictor = np.sum(loadings[jj] * f[ii], axis=1)
            monitor["log_likelihood"][chain, s] = interval_log_probability(
                bounds[jj, values - 1] - predictor, bounds[jj, values] - predictor
            ).sum()
            saved += 1
            raw_mean += (f - raw_mean) / saved
            delta = current_f - mean_f
            mean_f += delta / saved
            m2 += delta[:, :, None] * (current_f - mean_f)[:, None, :]
    partitions.flush()
    coordinates.flush()
    return SampleResult(
        draws,
        partitions,
        coordinates,
        occupancy,
        monitor,
        mean_f,
        m2 / (count - 1),
        {**mfm.diagnostics(), "structure": config.structure},
        accepted / max(moves, 1),
        raw_mean,
        demographic_draws,
    )
