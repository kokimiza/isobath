"""Restore/save full MFM draws and their explicit display mapping (§§4.2.1, 7)."""

import numpy as np

from isobath.inference.artifact import Model, validate

from .coordinates import projection
from .diagnostics import diagnose, probability_diagnostic
from .mfm import MFM
from .partitions import align, representative, vi


def build_model(data, result, *, version, seed, commit, saved_draws=200, mfm=None):
    partitions = result.partitions.reshape(-1, len(data.user_ids))
    reference, radius = representative(partitions)
    mfm = mfm or MFM()
    chains, steps = result.partitions.shape[:2]
    per_chain = max(1, min(steps, saved_draws // chains))
    selected = np.array(
        [
            c * steps + s
            for c in range(chains)
            for s in np.linspace(0, steps - 1, per_chain, dtype=int)
        ]
    )
    draws = [result.draws[i] for i in selected]
    s, j, d = len(draws), len(data.question_ids), data.dimension
    c = max(v["K"] for v in draws)
    arrays = {
        "draws_tau": np.empty((s, j, 4)),
        "draws_Lambda": np.empty((s, j, d)),
        "draws_w": np.zeros((s, c)),
        "draws_m": np.zeros((s, c, d)),
        "draws_Sigma": np.zeros((s, c, d, d)),
        "draws_valid": np.zeros((s, c), dtype=bool),
        "draws_occupied": np.zeros((s, c), dtype=bool),
        "draws_K": np.empty(s, dtype=int),
        "draws_T": np.empty(s, dtype=int),
        "draws_component_to_region": np.full((s, c), -3, dtype=int),
        "draws_core_z": np.empty((s, 0), dtype=int),
        "center_b": np.empty((s, d)),
        "scale_a": np.empty((s, d)),
        "P": projection(d, spatial=data.spatial),
        "c": np.zeros(3 if data.spatial else 2),
    }
    for i, (original, draw) in enumerate(zip(selected, draws, strict=True)):
        k, t = draw["K"], draw["T"]
        for key in ("tau", "Lambda"):
            arrays[f"draws_{key}"][i] = draw[key]
        for key in ("w", "m", "Sigma"):
            arrays[f"draws_{key}"][i, :k] = draw[key]
        arrays["draws_valid"][i, :k], arrays["draws_occupied"][i, :t] = True, True
        arrays["draws_K"][i], arrays["draws_T"][i] = k, t
        arrays["center_b"][i], arrays["scale_a"][i] = draw["b"], draw["a"]
        arrays["draws_component_to_region"][i, :t] = align(partitions[original], reference)
        arrays["draws_component_to_region"][i, t:k] = -2
    support, counts = np.unique(result.occupancy, return_counts=True)
    arrays["T_support"], arrays["T_post"] = support, counts / counts.sum()
    k_dist = {}
    for t, probability in zip(support, arrays["T_post"], strict=True):
        series = mfm.series(len(data.user_ids), int(t))
        for k, p in zip(series.support, series.probabilities, strict=True):
            k_dist[int(k)] = k_dist.get(int(k), 0.0) + float(probability * p)
    arrays["K_support"] = np.array(sorted(k_dist))
    arrays["K_post"] = np.array([k_dist[k] for k in arrays["K_support"]])
    if result.series.get("structure") != "mfm":
        arrays["K_support"], arrays["K_post"] = np.array([1]), np.ones(1)
    if result.series.get("structure") == "student":
        arrays["draws_nu"] = np.array([draw["nu"] for draw in draws])
    diagnostics = diagnose({**result.monitor, "T_N": result.occupancy})
    p, error = probability_diagnostic(result.occupancy >= 2)
    chain_references = [representative(z)[0] for z in result.partitions]
    chain_vi = max(vi(a, b, normalized=True) for a in chain_references for b in chain_references)
    diagnostics.update(
        p_multiple=p,
        p_multiple_mcse=error,
        credible_ball=radius,
        chain_vi=chain_vi,
        series=result.series,
        split_merge_acceptance=result.split_merge_acceptance,
    )
    diagnostics["accepted"] &= bool(abs(p - 0.5) > 3 * error and chain_vi <= 0.25)
    spread = float(np.median(np.sqrt(np.diagonal(result.latent_cov, axis1=1, axis2=2))))
    regions = [
        {"index": int(k), "lineage_id": f"{version}-R{k + 1}"} for k in range(reference.max() + 1)
    ]
    meta = {
        "schema_version": 4 if data.spatial else 3,
        "coordinate_system": "latent3-v1" if data.spatial else "D01-D04@1",
        "inference_mode": "cut",
        "seed": seed,
        "commit": commit,
        "n_observers": len(data.user_ids),
        "S": s,
        "C": c,
        "diagnostics": diagnostics,
        "projection_version": "identity3" if data.spatial else "D01-D04@1",
        "domain_order": ["X", "Y", "Z"] if data.spatial else [f"D{i + 1:02d}" for i in range(d)],
        "reference_artifact_id": version,
        "draw_chain": [v["chain"] for v in draws],
        "draw_iteration": [v["iteration"] for v in draws],
        "core_user_index": [],
        "provisional": bool(radius > 0.25 or spread > 0.5),
        "median_latent_sd": spread,
        "codes": {"alignment_unmatched": -1, "unseen": -2, "padding": -3},
        "sign_anchor_ids": [
            data.question_ids[np.flatnonzero(data.anchors & (data.domains == axis))[0]]
            for axis in range(d)
        ],
        "array_dtypes": {key: str(value.dtype) for key, value in arrays.items()},
    }
    model = Model(
        version, "CHARTED", data.item_set_version, meta, data.question_ids, arrays, regions
    )
    validate(model)
    return model
