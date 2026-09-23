"""Normal-inverse-Wishart conjugacy on the untransformed sampling scale (§§3, 4)."""

from dataclasses import dataclass

import numpy as np
from scipy.special import multigammaln
from scipy.stats import invwishart, multivariate_t


@dataclass(frozen=True)
class NIW:
    mean: np.ndarray
    kappa: float
    nu: float
    psi: np.ndarray

    @classmethod
    def default(cls, dimension: int):
        # d=16 gives nu=22, E[Sigma]=0.5 I, as specified.
        return cls(np.zeros(dimension), 0.1, dimension + 6.0, 2.5 * np.eye(dimension))

    def posterior(self, data):
        n = len(data)
        if n == 0:
            return self
        mean = np.mean(data, axis=0)
        centered = data - mean
        delta = mean - self.mean
        kappa = self.kappa + n
        return NIW(
            (self.kappa * self.mean + n * mean) / kappa,
            kappa,
            self.nu + n,
            self.psi + centered.T @ centered + self.kappa * n / kappa * np.outer(delta, delta),
        )

    def log_marginal(self, data):
        post, d, n = self.posterior(data), len(self.mean), len(data)
        return (
            -n * d / 2 * np.log(np.pi)
            + d / 2 * np.log(self.kappa / post.kappa)
            + self.nu / 2 * np.linalg.slogdet(self.psi)[1]
            - post.nu / 2 * np.linalg.slogdet(post.psi)[1]
            + multigammaln(post.nu / 2, d)
            - multigammaln(self.nu / 2, d)
        )

    def log_predictive(self, point, data):
        post = self.posterior(data)
        df = post.nu - len(self.mean) + 1
        scale = post.psi * (post.kappa + 1) / (post.kappa * df)
        return float(multivariate_t.logpdf(point, loc=post.mean, shape=scale, df=df))

    def sample(self, rng):
        cov = np.atleast_2d(invwishart.rvs(self.nu, self.psi, random_state=rng))
        return rng.multivariate_normal(self.mean, cov / self.kappa), cov
