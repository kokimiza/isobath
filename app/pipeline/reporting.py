"""Ordinal prior/posterior predictive checks; no missing-value imputation (§§9.4, 10)."""

import numpy as np


def _correlations(values):
    observed = values > 0
    safe = np.where(observed, values, 0).astype(float)
    mask = observed.astype(float)
    count = mask.T @ mask
    sums = safe.T @ mask
    squares = (safe**2).T @ mask
    products = safe.T @ safe
    with np.errstate(divide="ignore", invalid="ignore"):
        covariance = products - sums * sums.T / count
        variance = squares - sums**2 / count
        correlation = covariance / np.sqrt(variance * variance.T)
    return [[float(v) if np.isfinite(v) else None for v in row] for row in correlation]


def simulate_fitted(data, model, rng, draw=None):
    arrays = model.arrays
    draw = int(rng.integers(len(arrays["draws_K"]))) if draw is None else draw
    labels = rng.choice(len(arrays["draws_w"][draw]), len(data.user_ids), p=arrays["draws_w"][draw])
    scores = np.array(
        [
            rng.multivariate_normal(arrays["draws_m"][draw, c], arrays["draws_Sigma"][draw, c])
            for c in labels
        ]
    )
    if "draws_nu" in arrays:
        nu = arrays["draws_nu"][draw]
        centers = arrays["draws_m"][draw, labels]
        scores = (
            centers + (scores - centers) / np.sqrt(rng.chisquare(nu, len(scores)) / nu)[:, None]
        )
    latent_response = scores @ arrays["draws_Lambda"][draw].T + rng.normal(size=data.answers.shape)
    answers = 1 + np.sum(latent_response[:, :, None] > arrays["draws_tau"][draw], axis=2)
    answers[data.answers == 0] = 0
    return answers


def posterior_predictive_report(data, model, rng, replications=64, *, latent=None):
    observed = np.array([np.bincount(column, minlength=6)[1:] for column in data.answers.T])
    counts, correlations = [], []
    for _ in range(replications):
        answers = simulate_fitted(data, model, rng)
        counts.append([np.bincount(column, minlength=6)[1:] for column in answers.T])
        correlations.append(_correlations(answers))
    mask = (data.answers > 0).astype(int)
    strata, external = [], []
    if data.quality_scores is not None:
        for low, high in ((0.0, 0.75), (0.75, 0.9), (0.9, 1.01)):
            chosen = (data.quality_scores >= low) & (data.quality_scores < high)
            strata.append(
                {
                    "range": [low, high],
                    "people": int(chosen.sum()),
                    "category_counts": np.bincount(data.answers[chosen].ravel(), minlength=6)[
                        1:
                    ].tolist(),
                }
            )
        strata.append(
            {
                "range": None,
                "people": int(np.sum(~np.isfinite(data.quality_scores))),
                "category_counts": np.bincount(
                    data.answers[~np.isfinite(data.quality_scores)].ravel(), minlength=6
                )[1:].tolist(),
            }
        )
    if latent is not None:
        for question, answers in data.comparison_answers.items():
            valid = np.isfinite(answers)
            correlations_external = []
            for d in range(latent.shape[1]):
                value = (
                    np.corrcoef(answers[valid], latent[valid, d])[0, 1]
                    if valid.sum() >= 3
                    and np.std(answers[valid]) > 0
                    and np.std(latent[valid, d]) > 0
                    else np.nan
                )
                correlations_external.append(float(value) if np.isfinite(value) else None)
            external.append(
                {
                    "question_id": question,
                    "people": int(valid.sum()),
                    "latent_correlations": correlations_external,
                }
            )
    return {
        "replications": replications,
        "question_ids": data.question_ids,
        "observed_counts": observed.tolist(),
        "replicated_counts_interval": np.quantile(counts, [0.025, 0.5, 0.975], axis=0).tolist(),
        "coanswer_counts": (mask.T @ mask).tolist(),
        "observed_correlations": _correlations(data.answers),
        "replicated_correlations": correlations,
        "unverified": [
            "measurement invariance without demographic data",
            "non-MAR dropout",
            "longitudinal change",
        ],
        "quality_strata": strata,
        "comparison_scales": external,
    }
