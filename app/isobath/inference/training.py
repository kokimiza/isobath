"""Private per-person joint posterior handoff; only the batch can resolve research IDs."""

import hashlib
import json

import numpy as np

from .project import Placement


def fingerprint(model, answers):
    observed = sorted((q, int(v)) for q, v in answers.items() if q in model.index)
    content = json.dumps([model.item_set_version, observed], separators=(",", ":"))
    return hashlib.sha256(content.encode()).hexdigest()


def private_key(identifier):
    return hashlib.sha256(str(identifier).encode()).hexdigest()


def training_placement(directory, model, identifier, answers):
    path = directory / "people" / f"{private_key(identifier)}.npz"
    if not path.exists():
        return None
    info = json.loads(path.with_suffix(".json").read_text(encoding="utf-8"))
    if info["version"] != model.version or info["fingerprint"] != fingerprint(model, answers):
        return None
    with np.load(path, allow_pickle=False) as archive:
        mean, covariance, coordinates = (
            archive["latent_mean"],
            archive["latent_cov"],
            archive["draws_x"],
        )
    return Placement(
        mean,
        np.sqrt(np.diag(covariance)),
        coordinates.mean(axis=0),
        float(1 / (1 + np.trace(covariance) / len(mean))),
        info["memberships"],
        info["near_boundary"],
        info["unmatched"],
        coordinates,
        "joint",
        info["credible_region"],
    )
