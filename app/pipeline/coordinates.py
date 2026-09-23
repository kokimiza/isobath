"""Display transforms only. Never feed transformed values back into the sampler (§5)."""

import numpy as np


def projection(dimension=16):
    if dimension < 2:
        raise ValueError("projection needs at least two factors")
    p = np.zeros((2, dimension))
    p[0, 0], p[1, min(3, dimension - 1)] = 1, 1
    return p


def standardize(w, m, sigma, loadings, tau, f):  # noqa: PLR0917 - explicit model transform
    center = w @ m
    scale = np.sqrt(w @ (np.diagonal(sigma, axis1=1, axis2=2) + (m - center) ** 2))
    return {
        "b": center,
        "a": scale,
        "f": (f - center) / scale,
        "m": (m - center) / scale,
        "Sigma": sigma / scale[None, :, None] / scale[None, None, :],
        "Lambda": loadings * scale,
        "tau": tau - (loadings @ center)[:, None],
    }
