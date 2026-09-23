"""Fixed-model, equal-outer-weight cut inference for ordinal answers (§7.1)."""

from dataclasses import dataclass, replace

import arviz as az
import numpy as np

from .artifact import ALIGNMENT_UNMATCHED, UNSEEN, Model
from .ordinal import draw_categorical, log_normal, truncated_normal
from .regions import calibrated_region, credible_region

NEAR_BOUNDARY = 0.2


@dataclass(frozen=True)
class InferenceConfig:
    warmup: int = 100
    draws: int = 100
    chains: int = 4
    seed: int = 0

    def __post_init__(self):
        if self.warmup < 0 or self.draws < 2 or self.chains < 1 or self.seed < 0:
            raise ValueError("invalid inference configuration")


@dataclass
class PosteriorDraws:
    latent: np.ndarray
    coordinates: np.ndarray
    component: np.ndarray
    region: np.ndarray
    outer_id: np.ndarray
    inner_chain: np.ndarray

    @property
    def probabilities(self):
        labels, counts = np.unique(self.region, return_counts=True)
        return {int(k): float(v / len(self.region)) for k, v in zip(labels, counts, strict=True)}


@dataclass
class Placement:
    latent: np.ndarray
    latent_se: np.ndarray
    map_xy: np.ndarray
    confidence: float
    memberships: list[dict] | None
    near_boundary: bool | None
    unmatched: dict
    draws_x: np.ndarray
    inference_mode: str = "cut"
    credible_region: dict | None = None


def infer(model: Model, answers: dict[int, int], config=None) -> PosteriorDraws:
    config = config or InferenceConfig()
    if not model.can_place:
        raise ValueError("no fitted model")
    for value in answers.values():
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, np.integer))
            or not 1 <= value <= 5
        ):
            raise ValueError("answer category must be an integer in 1..5")
    questions = sorted(set(answers) & model.index.keys(), key=model.index.get)
    idx = np.array([model.index[q] for q in questions], dtype=int)
    y = np.array([answers[q] for q in questions], dtype=int)
    a = model.arrays
    outer, _, d = a["draws_Lambda"].shape
    total = outer * config.chains * config.draws
    latent = np.empty((total, d))
    component, region, outer_id, inner_chain = [np.empty(total, dtype=np.int32) for _ in range(4)]
    rng = np.random.default_rng(config.seed)
    cursor = 0
    for s in range(outer):
        valid = np.flatnonzero(a["draws_valid"][s])
        weights, means, covs = (
            a["draws_w"][s, valid],
            a["draws_m"][s, valid],
            a["draws_Sigma"][s, valid],
        )
        design, tau = a["draws_Lambda"][s, idx], a["draws_tau"][s, idx]
        bounds = np.column_stack([np.full(len(idx), -np.inf), tau, np.full(len(idx), np.inf)])
        if len(idx):
            inv = np.linalg.solve(covs, np.broadcast_to(np.eye(d), covs.shape))
            precision_chol = np.linalg.cholesky(inv + design.T @ design)
            information = np.einsum("kij,kj->ki", inv, means)
        for chain in range(config.chains):
            z = chain % len(valid)
            f = means[z].copy()
            for iteration in range(config.warmup + config.draws if len(idx) else config.draws):
                if len(idx):
                    ystar = truncated_normal(
                        rng,
                        design @ f,
                        1.0,
                        bounds[np.arange(len(y)), y - 1],
                        bounds[np.arange(len(y)), y],
                    )
                    z = draw_categorical(rng, np.log(weights) + log_normal(f, means, covs))
                    chol = precision_chol[z]
                    f = np.linalg.solve(
                        chol.T,
                        np.linalg.solve(chol, information[z] + design.T @ ystar)
                        + rng.normal(size=d),
                    )
                    if iteration < config.warmup:
                        continue
                else:
                    z = int(rng.choice(len(valid), p=weights))
                    f = rng.multivariate_normal(means[z], covs[z])
                latent[cursor], component[cursor] = f, valid[z]
                region[cursor] = a["draws_component_to_region"][s, valid[z]]
                outer_id[cursor], inner_chain[cursor] = s, chain
                cursor += 1
    return PosteriorDraws(
        latent, latent @ a["P"].T + a["c"], component, region, outer_id, inner_chain
    )


def summarize(model, result, inference_mode="cut"):
    f, covariance = result.latent.mean(axis=0), np.atleast_2d(np.cov(result.latent.T))
    probabilities = result.probabilities
    unmatched = {
        "alignment_unmatched": probabilities.get(ALIGNMENT_UNMATCHED, 0.0),
        "unseen": probabilities.get(UNSEEN, 0.0),
    }
    unmatched["total"] = sum(unmatched.values())
    members, near = None, None
    if model.has_regions:
        members = sorted(
            [
                {"lineage_id": r["lineage_id"], "p": probabilities.get(r["index"], 0.0)}
                for r in model.regions
            ],
            key=lambda v: -v["p"],
        )
        near = len(members) > 1 and members[0]["p"] - members[1]["p"] < NEAR_BOUNDARY
        members = members[:3]
    region = credible_region(result.coordinates)
    return Placement(
        f,
        np.sqrt(np.diag(covariance)),
        result.coordinates.mean(axis=0),
        float(1 / (1 + np.trace(covariance) / len(f))),
        members,
        near,
        unmatched,
        result.coordinates,
        inference_mode,
        region,
    )


def inference_diagnostics(model, result, config):
    inner, outer_means, outer_probabilities = [], [], []
    labels = [-2, -1, *[r["index"] for r in model.regions]]
    for s in range(len(model.arrays["draws_K"])):
        indices = result.outer_id == s
        latent = result.latent[indices].reshape(config.chains, config.draws, -1)
        regions = result.region[indices].reshape(config.chains, config.draws)
        variables = np.concatenate([latent, *[(regions == r)[..., None] for r in labels]], axis=2)
        constant = np.all(variables == variables[0, 0], axis=(0, 1))
        active = variables[:, :, ~constant]
        with np.errstate(divide="ignore", invalid="ignore"):
            rhat = np.asarray(az.rhat(active)) if active.size else np.ones(1)
            ess = (
                np.asarray(az.ess(active, method="bulk"))
                if active.size
                else np.array([config.chains * config.draws])
            )
            tail = (
                np.asarray(az.ess(active, method="tail", prob=(0.05, 0.95))) if active.size else ess
            )
        ok = bool(
            config.chains >= 2
            and np.isfinite(rhat).all()
            and rhat.max() < 1.01
            and ess.min() > 400
            and tail.min() > 400
        )
        inner.append(
            {
                "accepted": ok,
                "rhat_max": float(rhat.max()) if np.isfinite(rhat).all() else None,
                "ess_min": float(ess.min()) if np.isfinite(ess).all() else 0.0,
            }
        )
        outer_means.append(result.coordinates[indices].mean(axis=0))
        outer_probabilities.append([np.mean(regions == r) for r in labels])
    chains = np.array(model.meta.get("draw_chain", []))
    position_error = probability_error = np.inf
    if len(chains) == len(outer_means) and len(np.unique(chains)) >= 2:
        count = min(np.sum(chains == c) for c in np.unique(chains))
        if count >= 4:
            for values, kind in (
                (np.array(outer_means), "position"),
                (np.array(outer_probabilities), "probability"),
            ):
                batched = np.stack([values[chains == c][:count] for c in np.unique(chains)])
                active = ~np.all(batched == batched[0, 0], axis=(0, 1))
                error = (
                    float(np.max(az.mcse(batched[:, :, active], method="mean")))
                    if active.any()
                    else 0.0
                )
                if kind == "position":
                    position_error = error
                else:
                    probability_error = error
    return {
        "inner": inner,
        "outer_mcse_position": position_error if np.isfinite(position_error) else None,
        "outer_mcse_probability": probability_error if np.isfinite(probability_error) else None,
        "accepted": bool(
            all(r["accepted"] for r in inner)
            and position_error <= 0.02 / 3
            and probability_error <= 0.01 / 3
        ),
    }


def place(model, answers, *, config=None, verify=False):
    config = config or InferenceConfig()
    if not verify:
        return summarize(model, infer(model, answers, config))
    previous = None
    for attempt in range(5):
        cfg = replace(config, draws=config.draws * 2**attempt, warmup=config.warmup * 2**attempt)
        result = infer(model, answers, cfg)
        report = inference_diagnostics(model, result, cfg)
        if report["outer_mcse_position"] is not None and (
            report["outer_mcse_position"] > 0.02 / 3 or report["outer_mcse_probability"] > 0.01 / 3
        ):
            raise ValueError("stored outer draws insufficient; rebuild model with more draws")
        if previous is not None and report["accepted"]:
            location_change = np.max(
                np.abs(result.coordinates.mean(axis=0) - previous.coordinates.mean(axis=0))
            )
            labels = result.probabilities.keys() | previous.probabilities.keys()
            probability_change = max(
                abs(result.probabilities.get(k, 0) - previous.probabilities.get(k, 0))
                for k in labels
            )
            chains = np.array(model.meta["draw_chain"])[result.outer_id]
            grouped = [result.coordinates[chains == c] for c in np.unique(chains)]
            region = calibrated_region(np.stack(grouped))
            if location_change <= 0.02 and probability_change <= 0.01 and region["accepted"]:
                placement = summarize(model, result)
                region["inference_diagnostics"] = report
                placement.credible_region = region
                return placement
        previous = result
    raise ValueError("cut inference precision not reached; keep previous snapshot")


def posterior(model, answers, *, config=None):
    result = infer(model, answers, config)
    return result.latent.mean(axis=0), np.atleast_2d(np.cov(result.latent.T))
