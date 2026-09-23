"""Jaccard/Hungarian display identity inheritance, using shared active participants (§5.2)."""

import numpy as np
from scipy.optimize import linear_sum_assignment


def inherit_lineage(users, z, regions, old_users, old_z, old_regions):  # noqa: PLR0917
    old_index = {uid: i for i, uid in enumerate(old_users)}
    common = [(i, old_index[uid]) for i, uid in enumerate(users) if uid in old_index]
    counts = np.zeros((len(regions), len(old_regions)), dtype=int)
    for i, j in common:
        counts[z[i], old_z[j]] += 1
    union = counts.sum(axis=1)[:, None] + counts.sum(axis=0)[None, :] - counts
    scores = np.divide(counts, union, out=np.zeros_like(counts, dtype=float), where=union > 0)
    rows, cols = linear_sum_assignment(-scores)
    output = [dict(region) for region in regions]
    for row, col in zip(rows, cols, strict=True):
        if counts[row, col] > 0:
            output[row]["lineage_id"] = old_regions[col]["lineage_id"]
    events = []
    for row, region in enumerate(output):
        parents = np.flatnonzero(counts[row] > 0)
        kind = (
            "new"
            if len(parents) == 0
            else "merge"
            if len(parents) > 1
            else "split"
            if np.sum(counts[:, parents[0]] > 0) > 1
            else "continue"
        )
        events.append(
            {
                "lineage_id": region["lineage_id"],
                "kind": kind,
                "parents": [old_regions[p]["lineage_id"] for p in parents],
            }
        )
    return output, events
