"""Stable ordinal-probit numerical primitives (statistics.md §§2.1, 4.2).

Only batch and offline inference import SciPy; the API reads metadata/snapshots.
"""

import numpy as np
from scipy.special import log_ndtr, logsumexp
from scipy.stats import truncnorm


def interval_log_probability(lower, upper):
    lower, upper = np.broadcast_arrays(np.asarray(lower, float), np.asarray(upper, float))
    # Reflect right-tail intervals; subtract on the log scale to avoid 1 - 1.
    reflect = lower > 0
    lo = np.where(reflect, -upper, lower)
    hi = np.where(reflect, -lower, upper)
    log_hi, log_lo = log_ndtr(hi), log_ndtr(lo)
    with np.errstate(divide="ignore", invalid="ignore"):
        return log_hi + np.log(-np.expm1(log_lo - log_hi))


def truncated_normal(rng, mean, sd, lower, upper):
    mean, sd, lower, upper = np.broadcast_arrays(mean, sd, lower, upper)
    if np.any(sd <= 0) or np.any(lower >= upper):
        raise ValueError("invalid truncated normal interval")
    return np.asarray(
        truncnorm.rvs(
            (lower - mean) / sd, (upper - mean) / sd, loc=mean, scale=sd, random_state=rng
        )
    ).reshape(mean.shape)


def normal_from_precision(rng, precision, information):
    chol = np.linalg.cholesky(precision)
    mean = np.linalg.solve(chol.T, np.linalg.solve(chol, information))
    return mean + np.linalg.solve(chol.T, rng.normal(size=len(mean)))


def log_normal(point, means, covariances):
    delta = point - means
    chol = np.linalg.cholesky(covariances)
    whitened = np.linalg.solve(chol, delta[..., None])[..., 0]
    return -0.5 * (len(point) * np.log(2 * np.pi) + np.sum(whitened**2, axis=-1)) - np.log(
        np.diagonal(chol, axis1=-2, axis2=-1)
    ).sum(axis=-1)


def draw_categorical(rng, logp):
    return int(rng.choice(len(logp), p=np.exp(logp - logsumexp(logp))))
