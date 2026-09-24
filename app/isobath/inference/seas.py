"""Posterior-predictive sea cores in the same 3-D space as personal positions.

q_r(x) = E_theta[p(x, r | theta)] / E_theta[p(x | theta)].
A core contains x iff q_r(x) >= 1/2. Everything else is transitional/unmatched.
This differs deliberately from P(r | a person's answers), which integrates position.
"""

import numpy as np
from scipy.special import logsumexp
from scipy.stats import multivariate_normal


def probabilities(model, points):
    points = np.atleast_2d(points)
    if model.meta.get("schema_version") != 4 or not model.has_regions:
        return np.empty((len(points), 0))
    a = model.arrays
    ids = [r["index"] for r in model.regions]
    # The final column includes unoccupied and alignment-unmatched components.
    joint = np.full((len(points), len(ids) + 1), -np.inf)
    for s, valid in enumerate(a["draws_valid"]):
        for c in np.flatnonzero(valid & (a["draws_w"][s] > 0)):
            label = int(a["draws_component_to_region"][s, c])
            column = ids.index(label) if label in ids else len(ids)
            density = multivariate_normal.logpdf(
                points, mean=a["draws_m"][s, c], cov=a["draws_Sigma"][s, c]
            ) + np.log(a["draws_w"][s, c])
            joint[:, column] = np.logaddexp(joint[:, column], density)
    return np.exp(joint - logsumexp(joint, axis=1, keepdims=True))


def at_position(model, position):
    values = probabilities(model, [position])
    if not values.size:
        return None
    index = int(np.argmax(values[0]))
    p = float(values[0, index])
    return {
        "lineage_id": model.regions[index]["lineage_id"]
        if index < len(model.regions) and p >= 0.5
        else None,
        "p": p,
        "rule": "posterior_predictive_half",
    }


def sea_field(model, bins=21, extent=3.0):
    if not model.has_regions:
        return None
    axis = np.linspace(-extent, extent, bins)
    points = np.array(np.meshgrid(axis, axis, axis, indexing="ij")).reshape(3, -1).T
    values = probabilities(model, points)
    return {
        "bins": bins,
        "bounds": [[-extent, extent]] * 3,
        "threshold": 0.5,
        "rule": "posterior_predictive_half",
        "regions": [
            {"lineage_id": r["lineage_id"], "values": values[:, i].round(6).tolist()}
            for i, r in enumerate(model.regions)
        ],
    }
