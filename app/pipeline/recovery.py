"""Repeated cut-position checks with nested answer subsets (§9.2)."""

import numpy as np

from isobath.inference.project import InferenceConfig, infer, inference_diagnostics
from isobath.inference.regions import calibrated_region, contains

from .coordinates import projection, standardize


def cut_recovery(data, truth, model, rng, *, warmup=100, draws=100):
    component = int(rng.choice(len(truth["w"]), p=truth["w"]))
    f = rng.multivariate_normal(truth["m"][component], truth["Sigma"][component])
    response = truth["loadings"] @ f + rng.normal(size=len(data.question_ids))
    y = 1 + np.sum(response[:, None] > truth["tau"], axis=1)
    transformed = standardize(
        truth["w"], truth["m"], truth["Sigma"], truth["loadings"], truth["tau"], f[None, :]
    )
    target = transformed["f"] @ projection(data.dimension).T
    permutation = rng.permutation(len(y))
    records = []
    for count in sorted({min(n, len(y)) for n in (98, 49, 25)}, reverse=True):
        chosen = permutation[:count]
        answers = {data.question_ids[j]: int(y[j]) for j in chosen}
        config = InferenceConfig(warmup=warmup, draws=draws, seed=int(rng.integers(2**31)))
        posterior = infer(model, answers, config)
        chain = np.array(model.meta["draw_chain"])[posterior.outer_id]
        region = calibrated_region(
            np.stack([posterior.coordinates[chain == c] for c in np.unique(chain)])
        )
        records.append(
            {
                "answer_count": count,
                "covered": bool(contains(region, target)[0]),
                "area": region.get("area", 0.0),
                "variance_trace": float(np.trace(np.cov(posterior.coordinates.T))),
                "region_accepted": region["accepted"],
                "diagnostics": inference_diagnostics(model, posterior, config),
            }
        )
    return records
