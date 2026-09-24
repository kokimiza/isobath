"""Question-design prior, before any population fit. No invented observations or regions."""

import hashlib
import json

import numpy as np
from scipy.special import ndtri

from isobath.inference.artifact import Model, validate

from .coordinates import projection, standardize
from .data import Dataset, loading_mask, spatial_design
from .niw import NIW
from .sampler import measurement_priors


def design(questions, version):
    items = sorted(
        (q for q in questions if q["item_set_version"] == version and q["kind"] == "personality"),
        key=lambda q: q["id"],
    )
    # Explicit reproducible convention: first positively keyed common item per domain.
    anchors = []
    for d in range(1, 17):
        candidates = [
            q["id"] for q in items if q["domain"] == f"D{d:02d}" and q["keyed"] == 1 and q["anchor"]
        ]
        if not candidates:
            raise ValueError("each domain needs a positive common item as sign anchor")
        anchors.append(min(candidates))
    data = Dataset(
        np.zeros((1, len(items)), dtype=int),
        [q["id"] for q in items],
        ["design-only"],
        np.array([int(q["domain"][1:]) - 1 for q in items]),
        np.array([q["keyed"] for q in items]),
        np.array([q["id"] in anchors for q in items]),
        version,
    )
    data.validate()
    return data


def build(questions, version, draws=32):
    data = spatial_design(design(questions, version))
    d = data.dimension
    signature = json.dumps(
        [
            version,
            data.question_ids,
            data.domains.tolist(),
            data.signs.tolist(),
            data.anchors.tolist(),
        ]
    )
    digest = hashlib.sha256(signature.encode()).hexdigest()[:12]
    rng = np.random.default_rng(20260924)
    mean, variance = measurement_priors(data)
    prior = NIW.default(data.dimension)
    sampled = []
    for _ in range(draws):
        loadings = rng.normal(mean, np.sqrt(variance))
        loadings[~loading_mask(data)] = 0
        for j in np.flatnonzero(data.anchors):
            axis = data.domains[j]
            while data.signs[j] * loadings[j, axis] <= 0:
                loadings[j, axis] = rng.normal(mean[j, axis], np.sqrt(variance[j, axis]))
        tau = np.empty((len(data.question_ids), 4))
        for j in range(len(tau)):
            while True:
                trial = rng.normal(ndtri(np.arange(1, 5) / 5), 1.0)
                if np.all(np.diff(trial) > 0):
                    tau[j] = trial
                    break
        k = 1 + rng.poisson(1)
        w = rng.dirichlet(np.ones(k))
        parameters = [prior.sample(rng) for _ in range(k)]
        m, sigma = np.array([p[0] for p in parameters]), np.array([p[1] for p in parameters])
        sampled.append(standardize(w, m, sigma, loadings, tau, np.zeros((0, d))) | {"w": w})
    c = max(len(draw["w"]) for draw in sampled)
    a = {
        "draws_tau": np.array([v["tau"] for v in sampled]),
        "draws_Lambda": np.array([v["Lambda"] for v in sampled]),
        "draws_w": np.zeros((draws, c)),
        "draws_m": np.zeros((draws, c, d)),
        "draws_Sigma": np.zeros((draws, c, d, d)),
        "draws_valid": np.zeros((draws, c), dtype=bool),
        "draws_occupied": np.zeros((draws, c), dtype=bool),
        "draws_K": np.array([len(v["w"]) for v in sampled]),
        "draws_T": np.zeros(draws, dtype=int),
        "draws_component_to_region": np.full((draws, c), -3, dtype=int),
        "draws_core_z": np.empty((draws, 0), dtype=int),
        "center_b": np.array([v["b"] for v in sampled]),
        "scale_a": np.array([v["a"] for v in sampled]),
        "P": projection(d, spatial=True),
        "c": np.zeros(3),
        "T_support": np.array([0]),
        "T_post": np.ones(1),
    }
    for i, draw in enumerate(sampled):
        k = len(draw["w"])
        for key in ("w", "m", "Sigma"):
            a[f"draws_{key}"][i, :k] = draw[key]
        a["draws_valid"][i, :k] = True
        a["draws_component_to_region"][i, :k] = -2
    a["K_support"], counts = np.unique(a["draws_K"], return_counts=True)
    a["K_post"] = counts / draws
    model = Model(
        f"prior3-v1-{digest}",
        "PRIOR",
        version,
        {
            "schema_version": 4,
            "coordinate_system": "latent3-v1",
            "projection_version": "identity3",
            "inference_mode": "cut",
            "provisional": True,
            "basis": "question_design_prior",
            "n_observers": 0,
            "sign_anchor_ids": [
                data.question_ids[np.flatnonzero(data.anchors & (data.domains == axis))[0]]
                for axis in range(d)
            ],
        },
        data.question_ids,
        a,
        [],
    )
    validate(model)
    return model
