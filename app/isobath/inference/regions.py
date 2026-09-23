"""Empirical-mass ellipses and grid KDE regions (§6.3)."""

import arviz as az
import numpy as np
from scipy.stats import gaussian_kde


def contains(region, draws):
    if region["kind"] == "point":
        return np.all(np.isclose(draws, region["center"]), axis=1)
    if region["kind"] == "segment":
        endpoints = np.asarray(region["endpoints"])
        direction = endpoints[1] - endpoints[0]
        t = (draws - endpoints[0]) @ direction / (direction @ direction)
        return (t >= 0) & (t <= 1)
    indices = [
        np.searchsorted(e, draws[:, d], side="right") - 1 for d, e in enumerate(region["edges"])
    ]
    bins = region["bins"]
    inside = (indices[0] >= 0) & (indices[0] < bins) & (indices[1] >= 0) & (indices[1] < bins)
    return inside & np.isin(indices[0] * bins + indices[1], region["cells"])


def calibrated_region(chains, probability=0.95):
    """Split at independent chain boundaries, never alternate correlated draws."""
    chains = np.asarray(chains)
    if chains.ndim != 3 or chains.shape[0] < 2:
        raise ValueError("at least two independent chains required")
    half = chains.shape[0] // 2
    construction, evaluation = chains[:half].reshape(-1, 2), chains[half:].reshape(-1, 2)
    ess = (
        np.asarray(az.ess(chains[:half], method="bulk"))
        if chains.shape[1] >= 4
        else np.array([1.0])
    )
    effective_size = max(1.0, float(np.min(ess))) if np.isfinite(ess).all() else 1.0
    previous, stable = None, False
    for bins in (64, 128, 256):
        region = credible_region(construction, probability, bins, effective_size=effective_size)
        if region["kind"] != "grid_hpd":
            stable = True
            break
        if previous is not None:
            stable = (
                abs(region["area"] / previous["area"] - 1) <= 0.05
                and abs(region["mass"] - previous["mass"]) <= 0.01
            )
        if stable:
            break
        previous = region
    indicators = contains(region, evaluation).astype(float)
    # Batch-means MCSE also works without importing the offline ArviZ dependency.
    batches = np.array_split(indicators, max(2, min(20, len(indicators) // 10)))
    error = float(np.std([b.mean() for b in batches], ddof=1) / np.sqrt(len(batches)))
    mass = float(indicators.mean())
    region.update(
        validation_mass=mass,
        validation_mcse=error,
        chain_split="first_half/second_half",
        accepted=bool(stable and abs(mass - region["mass"]) <= max(0.01, 3 * error)),
        effective_size=effective_size,
    )
    return region


def ellipse(draws, probability=0.95):
    center = np.mean(draws, axis=0)
    cov = np.cov(draws.T)
    if np.linalg.matrix_rank(cov) < 2:
        return None
    delta = draws - center
    distances = np.einsum("ni,in->n", delta, np.linalg.solve(cov, delta.T))
    radius = float(np.quantile(distances, probability, method="higher"))
    return {
        "center": center.tolist(),
        "covariance": cov.tolist(),
        "radius_squared": radius,
        "mass": float(np.mean(distances <= radius)),
        "probability": probability,
    }


def credible_region(draws, probability=0.95, bins=64, effective_size=None):
    draws = np.asarray(draws, dtype=float)
    if draws.ndim != 2 or draws.shape[1] != 2 or len(draws) < 3 or not np.isfinite(draws).all():
        raise ValueError("finite two-dimensional draws required")
    center = draws.mean(axis=0)
    rank = np.linalg.matrix_rank(draws - center)
    if rank < 2:
        if rank == 0:
            return {"kind": "point", "center": center.tolist(), "mass": 1.0}
        _, _, basis = np.linalg.svd(draws - center, full_matrices=False)
        t = (draws - center) @ basis[0]
        ends = np.quantile(t, [(1 - probability) / 2, (1 + probability) / 2])
        return {
            "kind": "segment",
            "endpoints": (center + ends[:, None] * basis[0]).tolist(),
            "mass": probability,
        }
    kde = gaussian_kde(draws.T, bw_method=float(effective_size or len(draws)) ** (-1 / 6))
    margin = 5 * np.sqrt(np.diag(kde.covariance))
    lower, upper = draws.min(axis=0) - margin, draws.max(axis=0) + margin
    edges = [np.linspace(lo, hi, bins + 1) for lo, hi in zip(lower, upper, strict=True)]
    mid = [(e[1:] + e[:-1]) / 2 for e in edges]
    mesh = np.meshgrid(*mid, indexing="ij")
    area = np.prod((upper - lower) / bins)
    mass = kde(np.array(mesh).reshape(2, -1)) * area
    integral = mass.sum()
    mass /= integral
    sorted_mass = np.sort(mass)[::-1]
    threshold = sorted_mass[
        min(np.searchsorted(np.cumsum(sorted_mass), probability), len(mass) - 1)
    ]
    selected = mass >= threshold
    return {
        "kind": "grid_hpd",
        "edges": [e.tolist() for e in edges],
        "cells": np.flatnonzero(selected).tolist(),
        "bins": bins,
        "cell_probability": mass.tolist(),
        "mass": float(mass[selected].sum()),
        "probability": probability,
        "area": float(selected.sum() * area),
        "integration_error": abs(float(integral) - 1),
        "bandwidth": kde.covariance.tolist(),
        "ellipse": ellipse(draws, probability),
    }
