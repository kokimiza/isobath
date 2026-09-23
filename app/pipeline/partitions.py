"""Collapsed MFM local Gibbs and Jain-Neal (5,1,1) split/merge (§4.2).

Launch states are generated independently of the current split, conditional on the two
anchors and their union. Their density cancels in forward/reverse MH moves. The final
restricted sweep's probability must still be included.
"""

import numpy as np
from scipy.optimize import linear_sum_assignment
from scipy.special import logsumexp


def canonical(z):
    mapping = {}
    return np.array([mapping.setdefault(int(v), len(mapping)) for v in z], dtype=np.int32)


def categorical(logp, rng):
    logp = np.asarray(logp)
    return int(rng.choice(len(logp), p=np.exp(logp - logsumexp(logp))))


def log_target(x, z, prior, mfm):
    return mfm.log_partition(z) + sum(prior.log_marginal(x[z == c]) for c in np.unique(z))


def gibbs_partition(x, z, prior, mfm, rng):
    z = z.copy()
    for i in rng.permutation(len(z)):
        z[i] = -1
        labels = np.unique(z[z >= 0])
        logp = [
            np.log(np.sum(z == c) + mfm.gamma) + prior.log_predictive(x[i], x[z == c])
            for c in labels
        ]
        logp.append(
            np.log(mfm.gamma)
            + mfm.log_ratio(len(z), len(labels))
            + prior.log_predictive(x[i], x[:0])
        )
        choice = categorical(logp, rng)
        z[i] = labels[choice] if choice < len(labels) else max(labels, default=-1) + 1
        z = canonical(z)
    return z


def restricted_sweep(x, assignment, anchors, prior, gamma, rng, target=None):  # noqa: PLR0917 - MH forward/reverse contract
    assignment = assignment.copy()
    logq = 0.0
    for i in range(len(x)):
        if i in anchors:
            continue
        assignment[i] = -1
        logp = np.array(
            [
                np.log(np.sum(assignment == c) + gamma)
                + prior.log_predictive(x[i], x[assignment == c])
                for c in (0, 1)
            ]
        )
        logp -= logsumexp(logp)
        choice = int(target[i]) if target is not None else categorical(logp, rng)
        assignment[i] = choice
        logq += logp[choice]
    return assignment, float(logq)


def split_merge(x, z, prior, mfm, rng, launch_scans=5):  # noqa: PLR0917 - explicit kernel state
    if len(z) < 2:
        return z.copy(), False
    i, j = rng.choice(len(z), size=2, replace=False)
    idx = np.flatnonzero((z == z[i]) | (z == z[j]))
    anchors = (int(np.flatnonzero(idx == i)[0]), int(np.flatnonzero(idx == j)[0]))
    launch = rng.integers(0, 2, len(idx))
    launch[anchors[0]], launch[anchors[1]] = 0, 1
    for _ in range(launch_scans):
        launch, _ = restricted_sweep(x[idx], launch, anchors, prior, mfm.gamma, rng)
    proposal = z.copy()
    if z[i] == z[j]:
        split, logq = restricted_sweep(x[idx], launch, anchors, prior, mfm.gamma, rng)
        proposal[idx[split == 1]] = z.max() + 1
        correction = -logq
    else:
        target = (z[idx] == z[j]).astype(int)
        _, logq = restricted_sweep(x[idx], launch, anchors, prior, mfm.gamma, rng, target)
        proposal[idx] = z[i]
        correction = logq
    proposal = canonical(proposal)
    log_accept = log_target(x, proposal, prior, mfm) - log_target(x, z, prior, mfm) + correction
    accepted = np.log(rng.uniform()) < min(0.0, log_accept)
    return (proposal if accepted else z.copy()), bool(accepted)


def vi(a, b, normalized=False):
    if len(a) != len(b) or len(a) == 0:
        raise ValueError("partitions must have the same nonzero length")
    if len(a) == 1:
        return 0.0
    a, b = canonical(a), canonical(b)
    counts = np.zeros((a.max() + 1, b.max() + 1))
    np.add.at(counts, (a, b), 1)
    p = counts / len(a)
    pa, pb = p.sum(axis=1), p.sum(axis=0)
    r, c = np.nonzero(p)
    value = -np.sum(p[r, c] * np.log(p[r, c] ** 2 / (pa[r] * pb[c])))
    return float(max(0, value) / (np.log(len(a)) if normalized else 1))


def representative(draws):
    # Bound candidate memory while retaining an exact empirical loss for each candidate.
    indices = np.linspace(0, len(draws) - 1, min(64, len(draws)), dtype=int)
    candidates = np.unique(np.array([canonical(draws[i]) for i in indices]), axis=0)
    losses = [np.mean([vi(c, z) for z in draws]) for c in candidates]
    best = candidates[int(np.argmin(losses))]
    radius = float(
        np.quantile([vi(best, z, normalized=True) for z in draws], 0.95, method="higher")
    )
    return best, radius


def align(z, reference):
    z, reference = canonical(z), canonical(reference)
    table = np.zeros((z.max() + 1, reference.max() + 1), dtype=int)
    np.add.at(table, (z, reference), 1)
    rows, cols = linear_sum_assignment(-table)
    mapping = np.full(len(table), -1, dtype=np.int32)
    for r, c in zip(rows, cols, strict=True):
        if table[r, c] > 0:
            mapping[r] = c
    return mapping
