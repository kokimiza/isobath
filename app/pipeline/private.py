"""Private joint posterior files. These files must never be committed or served publicly."""

import json

import numpy as np

from isobath.inference.regions import calibrated_region
from isobath.inference.training import fingerprint, private_key

from .partitions import align, representative


def save_training(data, result, model, directory, *, require_precision=True):
    people = directory / "people"
    people.mkdir(parents=True, exist_ok=True)
    partitions = result.partitions.reshape(-1, len(data.user_ids))
    reference, _ = representative(partitions)
    mapped = np.lib.format.open_memmap(
        directory / "mapped-partitions.npy", mode="w+", dtype="int32", shape=partitions.shape
    )
    for s, z in enumerate(partitions):
        mapped[s] = align(z, reference)[z]
    for i, uid in enumerate(data.user_ids):
        coords = result.coordinates[:, :, i, :]
        region = calibrated_region(coords)
        if require_precision and not region["accepted"]:
            raise ValueError("personal credible region precision insufficient; increase draws")
        labels, counts = np.unique(mapped[:, i], return_counts=True)
        probabilities = dict(zip(map(int, labels), counts / len(partitions), strict=True))
        members = sorted(
            [
                {"lineage_id": r["lineage_id"], "p": float(probabilities.get(r["index"], 0.0))}
                for r in model.regions
            ],
            key=lambda r: -r["p"],
        )
        unmatched = float(probabilities.get(-1, 0.0))
        info = {
            "version": model.version,
            "inference_mode": "joint",
            "fingerprint": fingerprint(
                model,
                {q: int(v) for q, v in zip(data.question_ids, data.answers[i], strict=True) if v},
            ),
            "memberships": members[:3] if model.has_regions else None,
            "near_boundary": bool(len(members) > 1 and members[0]["p"] - members[1]["p"] < 0.2)
            if model.has_regions
            else None,
            "unmatched": {"alignment_unmatched": unmatched, "unseen": 0.0, "total": unmatched},
            "credible_region": region,
        }
        path = people / f"{private_key(uid)}.npz"
        np.savez(
            path,
            latent_mean=result.latent_mean[i],
            latent_cov=result.latent_cov[i],
            draws_x=coords.reshape(-1, coords.shape[-1]),
        )
        path.with_suffix(".json").write_text(json.dumps(info, allow_nan=False), encoding="utf-8")
    # Pseudonyms only, kept exclusively in the private research directory.
    (directory / "users.json").write_text(json.dumps(data.user_ids), encoding="utf-8")
    np.save(directory / "representative.npy", reference, allow_pickle=False)
