"""Miller & Harrison (2018), eqs. 3.1-3.2; statistics.md §2.2.

The Poisson tail is bounded after multiplication by the factorial terms, not beforehand.
"""

from dataclasses import dataclass

import numpy as np
from scipy.special import gammaln, logsumexp


@dataclass(frozen=True)
class Series:
    support: np.ndarray
    probabilities: np.ndarray
    log_value: float
    relative_error: float


class MFM:
    def __init__(self, gamma=1.0, poisson_mean=1.0, tolerance=1e-10, initial_limit=16):
        if gamma <= 0 or poisson_mean <= 0 or not 0 < tolerance <= 1e-8 or initial_limit < 1:
            raise ValueError("invalid MFM parameters")
        self.gamma = float(gamma)
        self.poisson_mean = float(poisson_mean)
        self.tolerance = tolerance
        self.initial_limit = initial_limit
        self._cache: dict[tuple[int, int], Series] = {}

    def _terms(self, n, t, k):
        return (
            gammaln(k + 1)
            - gammaln(k - t + 1)
            + gammaln(self.gamma * k)
            - gammaln(self.gamma * k + n)
            - self.poisson_mean
            + (k - 1) * np.log(self.poisson_mean)
            - gammaln(k)
        )

    def series(self, n: int, t: int) -> Series:
        if n < 0 or t < 0 or t > n + 1:
            raise ValueError("invalid sample size or occupancy")
        key = (n, t)
        if key in self._cache:
            return self._cache[key]
        limit = max(self.initial_limit, t + 1)
        while True:
            k = np.arange(max(t, 1), limit + 1)
            terms = self._terms(n, t, k)
            value = float(logsumexp(terms))
            q = self.poisson_mean * (limit + 2) / ((limit + 1) * (limit + 2 - t))
            error = np.inf
            if q < 1:
                error = float(np.exp(self._terms(n, t, limit + 1) - np.log1p(-q) - value))
            if error <= self.tolerance:
                result = Series(k, np.exp(terms - value), value, error)
                self._cache[key] = result
                return result
            limit *= 2

    def log_v(self, n, t):
        return self.series(n, t).log_value

    def log_ratio(self, n, t):
        return self.log_v(n, t + 1) - self.log_v(n, t)

    def log_partition(self, z):
        _, counts = np.unique(z, return_counts=True)
        return self.log_v(len(z), len(counts)) + np.sum(
            gammaln(counts + self.gamma) - gammaln(self.gamma)
        )

    def restore(self, counts, rng):
        result = self.series(int(np.sum(counts)), len(counts))
        k = int(rng.choice(result.support, p=result.probabilities))
        alpha = np.full(k, self.gamma)
        alpha[: len(counts)] += counts
        return k, rng.dirichlet(alpha)

    def diagnostics(self):
        return {
            "max_limit": max((int(s.support[-1]) for s in self._cache.values()), default=0),
            "max_relative_error": max((s.relative_error for s in self._cache.values()), default=0),
            "ratio_relative_error_bound": 2 * self.tolerance + self.tolerance**2,
        }
