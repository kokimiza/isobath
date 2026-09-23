"""Repeated-experiment statistics, kept distinct from MCMC uncertainty (§9.2)."""

import numpy as np
from scipy.special import ndtri

from .partitions import align, canonical


def wilson_interval(successes, repetitions, confidence=0.95):
    if repetitions < 1 or not 0 <= successes <= repetitions:
        raise ValueError("invalid binomial counts")
    z = ndtri((1 + confidence) / 2)
    p, denom = successes / repetitions, 1 + z * z / repetitions
    center = (p + z * z / (2 * repetitions)) / denom
    width = z * np.sqrt(p * (1 - p) / repetitions + z * z / (4 * repetitions**2)) / denom
    return float(center - width), float(center + width)


def calibration_summary(covered):
    n, successes = len(covered), sum(covered)
    lower, upper = wilson_interval(successes, n)
    p = successes / n
    return {
        "repetitions": n,
        "estimate": p,
        "interval": [lower, upper],
        "standard_error": float(np.sqrt(p * (1 - p) / n)),
        "accepted": bool(n >= 1000 and lower >= 0.92 and upper <= 0.98),
    }


def bootstrap_interval(values, rng, resamples=2000):
    values = np.asarray(values)
    means = [rng.choice(values, len(values), replace=True).mean() for _ in range(resamples)]
    return np.quantile(means, [0.025, 0.975]).tolist()


def total_variation(support_a, probabilities_a, support_b, probabilities_b):
    a, b = (
        dict(zip(support_a, probabilities_a, strict=True)),
        dict(zip(support_b, probabilities_b, strict=True)),
    )
    return 0.5 * sum(abs(a.get(k, 0) - b.get(k, 0)) for k in a.keys() | b.keys())


def membership_calibration(partitions, truth):
    truth = canonical(truth)
    categories = int(truth.max() + 2)
    probabilities = np.zeros((len(truth), categories))
    for partition in partitions:
        z = canonical(partition)
        mapped = align(z, truth)[z]
        mapped[mapped < 0] = categories - 1
        np.add.at(probabilities, (np.arange(len(truth)), mapped), 1 / len(partitions))
    target = np.eye(categories)[truth]
    bins = []
    for low in np.arange(0, 1, 0.1):
        mask = (probabilities >= low) & (
            probabilities <= 1 if low > 0.89 else probabilities < low + 0.1
        )
        if mask.any():
            bins.append(
                {
                    "mean_probability": float(probabilities[mask].mean()),
                    "frequency": float(target[mask].mean()),
                    "count": int(mask.sum()),
                }
            )
    return {
        "brier_score": float(np.mean(np.sum((probabilities - target) ** 2, axis=1))),
        "bins": bins,
        "unmatched_mass": float(probabilities[:, -1].mean()),
    }
