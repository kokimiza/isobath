"""Online placement: factor-model posterior on partial answers (design §5.8, D-4)."""

from dataclasses import dataclass

import numpy as np

from .artifact import Model

NEAR_BOUNDARY = 0.2


@dataclass
class Placement:
    latent: np.ndarray
    latent_se: np.ndarray
    map_xy: np.ndarray
    confidence: float
    memberships: list[dict] | None
    near_boundary: bool | None


def posterior(model: Model, answers: dict[int, int]) -> tuple[np.ndarray, np.ndarray]:
    """E[f | y_o] and Cov[f | y_o] for y = mu + Lambda f + e, f~N(0,I), e~N(0,diag(psi)).
    Unanswered items are simply dropped from the rows (ST-POS-02)."""
    a = model.arrays
    k = a["Lambda"].shape[1]
    idx = np.array([model.index[q] for q in answers if q in model.index], dtype=int)
    if idx.size == 0:
        return np.zeros(k), np.eye(k)
    raw = np.array([answers[q] for q in answers if q in model.index], dtype=float)
    z = (raw - a["mu"][idx]) / a["scale"][idx]
    L = a["Lambda"][idx]
    psi_inv = 1.0 / a["psi"][idx]
    cov = np.linalg.inv(np.eye(k) + L.T @ (L * psi_inv[:, None]))
    f = cov @ (L.T @ (psi_inv * z))
    return f, cov


def memberships(model: Model, f: np.ndarray, cov: np.ndarray) -> np.ndarray:
    """p(c | y) ∝ pi_c N(f; m_c, S_c + cov): posterior uncertainty flattens memberships."""
    a = model.arrays
    logp = []
    for pi, m, S in zip(a["gmm_pi"], a["gmm_mean"], a["gmm_cov"], strict=True):
        C = S + cov
        d = f - m
        _, logdet = np.linalg.slogdet(C)
        logp.append(np.log(pi) - 0.5 * (logdet + d @ np.linalg.solve(C, d)))
    logp = np.array(logp)
    p = np.exp(logp - logp.max())
    return p / p.sum()


def place(model: Model, answers: dict[int, int]) -> Placement:
    f, cov = posterior(model, answers)
    var = np.diag(cov)
    a = model.arrays
    members, near = None, None
    if model.has_regions:
        p = memberships(model, f, cov)
        order = np.argsort(p)[::-1]
        lineage = {r["index"]: r["lineage_id"] for r in model.regions}
        members = [
            {"lineage_id": lineage.get(int(i), f"R{int(i)}"), "p": round(float(p[i]), 4)}
            for i in order[:3]
        ]
        near = bool(len(p) > 1 and p[order[0]] - p[order[1]] < NEAR_BOUNDARY)
    return Placement(
        latent=f,
        latent_se=np.sqrt(var),
        map_xy=a["P"] @ f + a["c"],
        confidence=float(np.clip(1.0 - var.mean(), 0.0, 1.0)),
        memberships=members,
        near_boundary=near,
    )
