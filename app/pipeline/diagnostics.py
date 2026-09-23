"""Rank-normalized R-hat, bulk/tail ESS and MCSE gates (§4.3)."""

import arviz as az
import numpy as np


def diagnose(variables):
    report, accepted = {}, True
    for name, raw in variables.items():
        values = np.asarray(raw)
        if (
            values.ndim < 2
            or values.shape[0] < 2
            or values.shape[1] < 4
            or not np.isfinite(values).all()
        ):
            report[name] = {"accepted": False, "reason": "insufficient or nonfinite draws"}
            accepted = False
            continue
        flat = values.reshape(*values.shape[:2], -1)
        constant = np.all(flat == flat[0, 0], axis=(0, 1))
        active = flat[:, :, ~constant]
        if np.any(np.all(flat == flat[:, :1], axis=(0, 1)) & ~constant):
            report[name] = {"accepted": False, "reason": "chains stuck at different values"}
            accepted = False
            continue
        if active.size == 0:
            ok = name == "T_N"
            report[name] = {"accepted": ok, "constant": True, "mcse": 0.0}
            accepted &= ok
            continue
        rhat, bulk, tail, mcse = [
            np.asarray(v)
            for v in (
                az.rhat(active),
                az.ess(active, method="bulk"),
                az.ess(active, method="tail", prob=(0.05, 0.95)),
                az.mcse(active, method="mean"),
            )
        ]
        finite = all(np.isfinite(v).all() for v in (rhat, bulk, tail, mcse))
        ok = bool(finite and rhat.max() < 1.01 and bulk.min() > 400 and tail.min() > 400)
        report[name] = {
            "accepted": ok,
            "constant_dimensions": int(constant.sum()),
            "rhat_max": float(rhat.max()) if np.isfinite(rhat).all() else None,
            "ess_bulk_min": float(bulk.min()) if np.isfinite(bulk).all() else None,
            "ess_tail_min": float(tail.min()) if np.isfinite(tail).all() else None,
            "mcse": float(mcse.max()) if np.isfinite(mcse).all() else None,
        }
        accepted &= ok
    return {"accepted": bool(accepted and report), "variables": report}


def require_convergence(report):
    if not report.get("accepted"):
        raise ValueError("convergence requirements not met; artifact publication refused")


def probability_diagnostic(indicators):
    p = float(np.mean(indicators))
    if np.all(indicators == indicators.flat[0]):
        return p, 0.0
    error = float(np.asarray(az.mcse(indicators.astype(float), method="mean")))
    return p, error


def count_refit_mcse(first, second):
    """Conservative MC uncertainty for TV, summing category-wise independent-run errors."""
    support = np.union1d(first, second)
    error = 0.0
    for value in support:
        _, ea = probability_diagnostic(first == value)
        _, eb = probability_diagnostic(second == value)
        error += 0.5 * np.hypot(ea, eb)
    return float(error)


def unseen_prediction(occupancy, n, mfm):
    lookup = {}
    for t in np.unique(occupancy):
        series = mfm.series(n, int(t))
        lookup[int(t)] = float(
            series.probabilities
            @ (mfm.gamma * (series.support - t) / (n + mfm.gamma * series.support))
        )
    values = np.array([lookup[int(t)] for t in occupancy.ravel()]).reshape(occupancy.shape)
    error = 0.0 if np.all(values == values.flat[0]) else float(az.mcse(values, method="mean"))
    return float(values.mean()), error
