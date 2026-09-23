"""Prespecified prior sensitivity comparisons, statistics.md §9.5."""

from dataclasses import replace

from .diagnostics import require_convergence
from .export import build_model
from .mfm import MFM
from .sampler import sample
from .validation import total_variation


def sensitivity_experiment(data, config, directory):
    settings = [("baseline", config)]
    for name, values in {
        "poisson_mean": (0.5, 2.0),
        "gamma": (0.5, 2.0),
        "main_loading_mean": (0.4, 0.8),
        "main_loading_sd": (0.2, 0.5),
        "within_variance": (0.25, 1.0),
        "kappa": (0.05, 0.2),
    }.items():
        settings.extend((f"{name}-{value}", replace(config, **{name: value})) for value in values)
    results, baseline = [], None
    for label, cfg in settings:
        sampled = sample(data, cfg, directory / label)
        model = build_model(
            data,
            sampled,
            version=label,
            seed=cfg.seed,
            commit="sensitivity",
            mfm=MFM(cfg.gamma, cfg.poisson_mean, cfg.series_tolerance, cfg.series_limit),
        )
        require_convergence(model.meta["diagnostics"])
        baseline = model if baseline is None else baseline
        a, b = model.arrays, baseline.arrays
        results.append(
            {
                "setting": label,
                "T_support": a["T_support"].tolist(),
                "T_post": a["T_post"].tolist(),
                "K_support": a["K_support"].tolist(),
                "K_post": a["K_post"].tolist(),
                "tv_T": total_variation(a["T_support"], a["T_post"], b["T_support"], b["T_post"]),
                "display_changed": model.has_regions != baseline.has_regions,
                "representative_count": len(model.regions),
                "diagnostics": model.meta["diagnostics"],
            }
        )
    return {"comparisons": results}
