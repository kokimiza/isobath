"""Respondent-split sample-size experiments (§0.3).

Bootstrap repetitions resample respondents within the already separated pools and refit
every model. Nested samples within a repetition are deliberately dependent.
"""

from dataclasses import replace

import numpy as np
from scipy.optimize import linear_sum_assignment

from .diagnostics import require_convergence
from .export import build_model
from .partitions import representative, vi
from .reporting import simulate_fitted
from .research import predictive_density, respondent_split, stability_decision, subset
from .sampler import sample
from .validation import total_variation


def nested_design(n, sizes, rng):
    train, replicate, holdout = respondent_split(n, rng)
    if sorted(set(sizes)) != list(sizes) or max(sizes) > min(len(train), len(replicate)):
        raise ValueError("sizes must increase and fit disjoint training/replication pools")
    return [
        {"train": train[:size], "replicate": replicate[:size], "holdout": holdout} for size in sizes
    ]


def profile_comparison(a, b, weights_a, weights_b):
    cost = np.sqrt(np.mean((a[:, None, :] - b[None, :, :]) ** 2, axis=2))
    rows, cols = linear_sum_assignment(cost)
    unmatched = max(
        sum(weights_a[i] for i in range(len(a)) if i not in rows),
        sum(weights_b[i] for i in range(len(b)) if i not in cols),
    )
    return float(cost[rows, cols].max()), float(unmatched)


def _estimate(data, config, directory, tag):
    result = sample(data, config, directory)
    model = build_model(data, result, version=tag, seed=config.seed, commit="study")
    require_convergence(model.meta["diagnostics"])
    reference, _ = representative(result.partitions.reshape(-1, len(data.user_ids)))
    profiles = np.array(
        [result.raw_latent_mean[reference == k].mean(axis=0) for k in range(reference.max() + 1)]
    )
    weights = np.bincount(reference) / len(reference)
    return model, profiles, weights, result, reference


def sample_size_experiment(
    data, sizes, config, directory, *, repetitions=100, integration_samples=2048
):
    rng = np.random.default_rng(config.seed)
    design = nested_design(len(data.user_ids), sizes, rng)
    pools = {role: design[-1][role] for role in ("train", "replicate", "holdout")}
    results = []
    for repetition in range(repetitions):
        # First run is the observed estimate; subsequent runs refit respondent bootstraps.
        sampled = {
            role: values if repetition == 0 else rng.choice(values, len(values), replace=True)
            for role, values in pools.items()
        }
        previous, comparisons = None, []
        for size in sizes:
            train = subset(data, sampled["train"][:size])
            replicate = subset(data, sampled["replicate"][:size])
            train.user_ids = [f"{uid}-bootstrap-{i}" for i, uid in enumerate(train.user_ids)]
            replicate.user_ids = [
                f"{uid}-bootstrap-{i}" for i, uid in enumerate(replicate.user_ids)
            ]
            work = directory / f"repetition-{repetition}" / f"n-{size}"
            cfg = replace(config, seed=int(rng.integers(2**31)))
            fit = _estimate(train, cfg, work / "mfm", "mfm")
            replication = _estimate(
                replicate, replace(cfg, seed=cfg.seed + 1), work / "replication", "replication"
            )
            baselines = [
                _estimate(train, replace(cfg, structure=kind), work / kind, kind)[0]
                for kind in ("normal", "student")
            ]
            holdout = [
                {q: int(v) for q, v in zip(data.question_ids, data.answers[i], strict=True) if v}
                for i in sampled["holdout"]
            ]
            logp, errors = [], []
            for model in [fit[0], *baselines]:
                predictions = [
                    predictive_density(model, y, rng, integration_samples) for y in holdout
                ]
                logp.append(np.array([r["log_density"] for r in predictions]))
                errors.append(max(r["integration_mcse"] for r in predictions))
            replication_distance, replication_missing = profile_comparison(
                fit[1], replication[1], fit[2], replication[2]
            )
            if previous is not None:
                distance, missing = profile_comparison(
                    previous[0][1], fit[1], previous[0][2], fit[2]
                )
                a, b = previous[0][0].arrays, fit[0].arrays
                ar, br = fit[0].arrays, replication[0].arrays
                comparisons.append(
                    {
                        "tv_upper": max(
                            total_variation(
                                a["T_support"], a["T_post"], b["T_support"], b["T_post"]
                            ),
                            total_variation(
                                ar["T_support"], ar["T_post"], br["T_support"], br["T_post"]
                            ),
                        ),
                        "profile_upper": max(distance, replication_distance),
                        "unmatched_upper": max(missing, replication_missing),
                        "predictive_change_upper": abs(float(logp[0].mean() - previous[1].mean())),
                        "normal_gain_lower": float(np.mean(logp[0] - logp[1])),
                        "student_gain_lower": float(np.mean(logp[0] - logp[2])),
                        "independent_replication": True,
                        "has_regions": fit[0].has_regions,
                        "integration_mcse_max": max(errors),
                    }
                )
            previous = fit, logp[0]
        results.append(comparisons)
    intervals = []
    for i in range(len(sizes) - 1):
        row = {}
        for key in results[0][i]:
            values = [r[i][key] for r in results]
            if key in ("independent_replication", "has_regions"):
                row[key] = all(values)
            else:
                row[key] = float(np.quantile(values, 0.025 if key.endswith("_lower") else 0.95))
        intervals.append(row)
    return {
        "repetitions": repetitions,
        "sizes": sizes,
        "comparison_intervals": intervals,
        "profile_scale": "untransformed-prior-scale@1",
        "bootstrap_unit": "respondent-with-refitting",
        "supported": bool(
            repetitions >= 100
            and stability_decision(intervals)
            and all(r["integration_mcse_max"] <= 0.05 / 3 for r in intervals)
        ),
        "replicates": results,
    }


def hierarchy_statistic(data, config, directory):
    """Repeat parent selection and all child fits; singleton parents have zero improvement."""
    parent = _estimate(data, config, directory / "parent", "parent")
    improvements = []
    for label in np.unique(parent[4]):
        indices = np.flatnonzero(parent[4] == label)
        if len(indices) < 2:
            improvements.append(0.0)
            continue
        child = _estimate(
            subset(data, indices), config, directory / f"child-{label}", f"child-{label}"
        )
        draws = child[3].partitions.reshape(-1, len(indices))
        improvements.append(
            float(
                np.mean([vi(np.zeros(len(indices), dtype=int), z) - vi(child[4], z) for z in draws])
            )
        )
    return max(improvements, default=0.0)


def hierarchy_experiment(data, config, directory, *, repetitions=1000):
    rng = np.random.default_rng(config.seed)
    train, replicate, _ = respondent_split(len(data.user_ids), rng)
    first, second = subset(data, train), subset(data, replicate)
    observed = hierarchy_statistic(first, config, directory / "observed")
    replication = hierarchy_statistic(
        second, replace(config, seed=config.seed + 1), directory / "replication"
    )
    controls = {}
    for kind in ("normal", "student"):
        baseline = _estimate(first, replace(config, structure=kind), directory / kind, kind)[0]
        statistics = []
        for r in range(repetitions):
            null = replace(first, answers=simulate_fitted(first, baseline, rng))
            statistics.append(
                hierarchy_statistic(
                    null,
                    replace(config, seed=int(rng.integers(2**31))),
                    directory / kind / f"null-{r}",
                )
            )
        controls[kind] = {
            "maximum_statistic_95": float(np.quantile(statistics, 0.95)),
            "p_value": float((1 + sum(v >= observed for v in statistics)) / (repetitions + 1)),
            "statistics": statistics,
        }
    return {
        "observed": observed,
        "independent_replication": replication,
        "repetitions": repetitions,
        "null": controls,
        "passes_selection_null": bool(
            repetitions >= 1000
            and all(
                min(observed, replication) > v["maximum_statistic_95"] for v in controls.values()
            )
        ),
        "interpretation": "Selection-adjusted evidence; also require profile/stability criteria from the study command.",
    }
