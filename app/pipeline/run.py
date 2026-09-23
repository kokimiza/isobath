"""Offline CLI. Never changes CURRENT. Reproducible reports contain no contact identity.

uv run --group pipeline python -m pipeline.run --help
"""

import argparse
import json
import logging
import os
import shutil
import subprocess
from dataclasses import replace
from datetime import datetime
from pathlib import Path

import numpy as np
import psycopg
from psycopg.rows import dict_row

from isobath.inference.artifact import load, save, validate_version
from isobath.inference.regions import calibrated_region, contains

from .coordinates import projection, standardize
from .data import extract, from_records
from .diagnostics import count_refit_mcse, require_convergence, unseen_prediction
from .export import build_model
from .lineage import inherit_lineage
from .mfm import MFM
from .partitions import representative, vi
from .private import save_training
from .recovery import cut_recovery
from .reporting import posterior_predictive_report
from .research import simulate_prior
from .sampler import SamplerConfig, sample
from .sensitivity import sensitivity_experiment
from .study import hierarchy_experiment, sample_size_experiment
from .validation import (
    calibration_summary,
    membership_calibration,
    total_variation,
    wilson_interval,
)

log = logging.getLogger(__name__)


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8"
    )
    temporary.replace(path)


def git_commit():
    executable = shutil.which("git")
    if executable is None:
        raise ValueError("git is required to record the implementation commit")
    return subprocess.run(  # noqa: S603 - fixed argument vector, resolved git executable
        [executable, "rev-parse", "HEAD"], check=True, capture_output=True, text=True
    ).stdout.strip()


def fit(data, config, version, root, private_root, *, commit, saved_draws=200, previous=None):
    validate_version(version)
    if private_root.resolve().is_relative_to(root.resolve()):
        raise ValueError("private results must be outside the model artifact root")
    work = private_root / f"chart-{version}"
    work.mkdir(parents=True, exist_ok=False)
    result = sample(data, config, work / "chains")
    mfm = MFM(config.gamma, config.poisson_mean, config.series_tolerance, config.series_limit)
    model = build_model(
        data,
        result,
        version=version,
        seed=config.seed,
        commit=commit,
        saved_draws=saved_draws,
        mfm=mfm,
    )
    write_json(work / "diagnostics.json", model.meta["diagnostics"])
    write_json(
        work / "predictive-checks.json",
        posterior_predictive_report(
            data, model, np.random.default_rng(config.seed), latent=result.raw_latent_mean
        ),
    )
    require_convergence(model.meta["diagnostics"])
    if previous:
        old = load(root, previous, metadata_only=True)
        old_work = private_root / f"chart-{previous}"
        old_users = json.loads((old_work / "users.json").read_text(encoding="utf-8"))
        old_z = np.load(old_work / "representative.npy", allow_pickle=False)
        reference, _ = representative(result.partitions.reshape(-1, len(data.user_ids)))
        model.regions, model.meta["lineage_events"] = inherit_lineage(
            data.user_ids, reference, model.regions, old_users, old_z, old.regions
        )
    # An independent re-fit checks actual posterior sensitivity, not just prior tail mass.
    expanded = replace(
        config,
        seed=config.seed + 1,
        series_limit=2 * result.series["max_limit"],
        series_tolerance=config.series_tolerance / 10,
    )
    verification = sample(data, expanded, work / "expanded")
    other = build_model(
        data,
        verification,
        version=version,
        seed=expanded.seed,
        commit=commit,
        saved_draws=saved_draws,
        mfm=MFM(
            expanded.gamma, expanded.poisson_mean, expanded.series_tolerance, expanded.series_limit
        ),
    )
    require_convergence(other.meta["diagnostics"])
    changes = {
        name: total_variation(
            model.arrays[f"{name}_support"],
            model.arrays[f"{name}_post"],
            other.arrays[f"{name}_support"],
            other.arrays[f"{name}_post"],
        )
        for name in ("T", "K")
    }
    model.meta["diagnostics"]["series_refit"] = changes
    count_error = count_refit_mcse(result.occupancy, verification.occupancy)
    model.meta["diagnostics"]["series_refit"]["T_mcse_bound"] = count_error
    # K|T is the same Markov kernel in both runs; TV contracts under that kernel.
    model.meta["diagnostics"]["series_refit"]["K_mcse_bound"] = count_error
    unseen, unseen_error = unseen_prediction(result.occupancy, len(data.user_ids), mfm)
    other_unseen, other_error = unseen_prediction(verification.occupancy, len(data.user_ids), mfm)
    model.meta["diagnostics"]["series_refit"]["unseen_prior_predictive_difference"] = abs(
        unseen - other_unseen
    )
    model.meta["diagnostics"]["series_refit"]["unseen_mcse"] = float(
        np.hypot(unseen_error, other_error)
    )
    if abs(unseen - other_unseen) > 0.005 or np.hypot(unseen_error, other_error) > 0.005 / 3:
        raise ValueError("unseen predictive mass unstable under series expansion")
    if count_error > 0.01 / 3:
        raise ValueError("series expansion comparison has excessive Monte Carlo error")
    if max(changes.values()) > 0.01 or model.has_regions != other.has_regions:
        raise ValueError("series expansion changed posterior or display; increase sampling")
    save_training(data, result, model, work)
    model.meta["private_results_required"] = True
    return save(model, root)


def validation_run(args):
    rng = np.random.default_rng(args.seed)
    records, covered = [], []
    for repetition in range(args.repetitions):
        components = (
            None
            if args.mode in ("prior", "sbc")
            else (3 if args.condition in ("separated", "overlap") else 1)
        )
        data, truth = simulate_prior(
            args.people,
            args.items,
            args.dimensions,
            rng,
            components=components,
            separation=4.0 if args.condition == "separated" else 0.5,
            condition=args.condition
            if args.condition in ("heavy_tail", "skew", "local_dependence", "careless")
            else "normal",
        )
        if args.mode == "prior":
            counts = np.bincount(data.answers[data.answers > 0], minlength=6)[1:]
            records.append({"category_counts": counts.tolist(), "K": truth["K"]})
            continue
        directory = args.private_root / f"{args.mode}-{args.seed}-{repetition}"
        config = SamplerConfig(warmup=args.warmup, draws=args.draws, seed=args.seed + repetition)
        result = sample(data, config, directory)
        model = build_model(
            data, result, version=f"sim-{repetition}", seed=config.seed, commit=git_commit()
        )
        row = {"diagnostics": model.meta["diagnostics"]}
        if args.mode == "sbc":
            # Raw-scale identifiable scalar ranks; randomized ranks for discrete K/T.
            row["ranks"] = {
                key: np.sum(value.reshape((-1, *value.shape[2:])) < truth[key], axis=0).tolist()
                for key, value in result.monitor.items()
                if key in truth
            }
            flat_t = result.occupancy.ravel()
            true_t = len(np.unique(truth["z"]))
            row["T_rank"] = int(
                np.sum(flat_t < true_t) + rng.integers(np.sum(flat_t == true_t) + 1)
            )
        else:
            reference, radius = representative(result.partitions.reshape(-1, args.people))
            distance = vi(reference, truth["z"], normalized=True)
            row.update(
                partition_vi=distance,
                ball_coverage=bool(distance <= radius),
                detected=model.has_regions,
                count_error=int(len(np.unique(reference)) - len(np.unique(truth["z"]))),
                overconcentrated=bool(distance > 0.25 and radius <= 0.05),
                membership_calibration=membership_calibration(
                    result.partitions.reshape(-1, args.people), truth["z"]
                ),
            )
            transformed = standardize(
                truth["w"], truth["m"], truth["Sigma"], truth["loadings"], truth["tau"], truth["f"]
            )
            true_xy = transformed["f"] @ projection(args.dimensions).T
            person_coverage = []
            for person in range(args.people):
                region = calibrated_region(result.coordinates[:, :, person, :])
                person_coverage.append(bool(contains(region, true_xy[person : person + 1])[0]))
            row["position_coverage"] = float(np.mean(person_coverage))
            row["cut_positions"] = cut_recovery(
                data, truth, model, rng, warmup=args.warmup, draws=args.draws
            )
            # One randomly preselected person per independent experiment for binomial CI.
            covered.append(person_coverage[0])
        records.append(row)
    report = {
        "mode": args.mode,
        "condition": args.condition,
        "seed": args.seed,
        "repetitions": args.repetitions,
        "acceptance_run": args.repetitions >= 1000 and args.mode == "recovery",
        "records": records,
        "sampling": {"warmup": args.warmup, "draws": args.draws},
        "all_converged": all(r.get("diagnostics", {}).get("accepted", False) for r in records),
    }
    if covered:
        report["coverage"] = calibration_summary(covered)
        report["coverage"]["accepted"] &= report["all_converged"]
        detected = sum(r["detected"] for r in records)
        interval = wilson_interval(detected, len(records), confidence=0.90)
        report["detection"] = {
            "estimate": detected / len(records),
            "one_sided_95_bounds": list(interval),
            "accepted": bool(
                report["all_converged"]
                and len(records) >= 1000
                and (
                    interval[1] <= 0.05
                    if args.condition == "one"
                    else interval[0] >= 0.90
                    if args.condition == "separated"
                    else False
                )
            ),
        }
        report["ball_coverage"] = calibration_summary([r["ball_coverage"] for r in records])
        report["ball_coverage"]["accepted"] &= report["all_converged"]
        counts = sorted({v["answer_count"] for r in records for v in r["cut_positions"]})
        report["cut_coverage"] = {}
        for count in counts:
            rows = [v for r in records for v in r["cut_positions"] if v["answer_count"] == count]
            summary = calibration_summary([v["covered"] for v in rows])
            summary["mean_area"] = float(np.mean([v["area"] for v in rows]))
            summary["mean_variance_trace"] = float(np.mean([v["variance_trace"] for v in rows]))
            summary["accepted"] &= bool(
                report["all_converged"]
                and all(v["region_accepted"] and v["diagnostics"]["accepted"] for v in rows)
            )
            report["cut_coverage"][count] = summary
    write_json(args.output, report)
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(prog="pipeline.run")
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("fit", "simulate-fit", "validate", "study", "sensitivity", "hierarchy"):
        p = sub.add_parser(command)
        p.add_argument("--seed", type=int, default=0)
        p.add_argument("--warmup", type=int, default=1000)
        p.add_argument("--draws", type=int, default=1000)
        p.add_argument("--private-root", type=Path, default=Path(".private-statistics"))
        if command in ("simulate-fit", "validate"):
            p.add_argument("--people", type=int, default=100)
            p.add_argument("--items", type=int, default=20)
            p.add_argument("--dimensions", type=int, default=4)
        if command in ("fit", "simulate-fit"):
            p.add_argument("--version", required=True)
            p.add_argument("--root", type=Path, default=Path("models"))
            p.add_argument("--previous")
            p.add_argument("--saved-draws", type=int, default=200)
        if command in ("fit", "study", "sensitivity", "hierarchy"):
            p.add_argument(
                "--input",
                type=Path,
                help="Private consent-snapshot JSON; otherwise read analysis views",
            )
            p.add_argument("--item-set-version", default="0.2")
            p.add_argument("--sign-anchors", type=int, nargs="+", required=True)
            p.add_argument("--cutoff", type=datetime.fromisoformat, required=True)
            p.add_argument("--min-quality", type=float, default=0.0)
        if command == "study":
            p.add_argument("--sizes", type=int, nargs="+", required=True)
            p.add_argument("--repetitions", type=int, default=100)
            p.add_argument("--output", type=Path, required=True)
        if command in ("sensitivity", "hierarchy"):
            p.add_argument("--output", type=Path, required=True)
        if command == "hierarchy":
            p.add_argument("--repetitions", type=int, default=1000)
        if command == "validate":
            p.add_argument("--mode", choices=["prior", "sbc", "recovery"], required=True)
            p.add_argument(
                "--condition",
                choices=[
                    "one",
                    "separated",
                    "overlap",
                    "heavy_tail",
                    "skew",
                    "local_dependence",
                    "careless",
                ],
                default="one",
            )
            p.add_argument("--repetitions", type=int, default=1000)
            p.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "validate":
            return validation_run(args)
        if args.command == "simulate-fit":
            data, _ = simulate_prior(
                args.people, args.items, args.dimensions, np.random.default_rng(args.seed)
            )
        else:
            if args.cutoff.tzinfo is None:
                raise ValueError("cutoff must include a time zone")
            if args.input:
                payload = json.loads(args.input.read_text(encoding="utf-8"))
                payload["responses"] = [
                    r
                    for r in payload["responses"]
                    if datetime.fromisoformat(r["completed_at"]) < args.cutoff
                ]
                data = from_records(
                    payload["responses"],
                    payload["questions"],
                    payload["participants"],
                    payload["tombstones"],
                    args.item_set_version,
                    set(args.sign_anchors),
                    args.min_quality,
                )
            else:
                with psycopg.connect(
                    os.environ["PIPELINE_DATABASE_URL"], row_factory=dict_row
                ) as conn:
                    data = extract(
                        conn,
                        args.item_set_version,
                        set(args.sign_anchors),
                        args.cutoff,
                        args.min_quality,
                    )
        config = SamplerConfig(warmup=args.warmup, draws=args.draws, seed=args.seed)
        if args.command == "study":
            report = sample_size_experiment(
                data, args.sizes, config, args.private_root / "study", repetitions=args.repetitions
            )
            write_json(args.output, report)
        elif args.command == "sensitivity":
            write_json(
                args.output, sensitivity_experiment(data, config, args.private_root / "sensitivity")
            )
        elif args.command == "hierarchy":
            write_json(
                args.output,
                hierarchy_experiment(
                    data, config, args.private_root / "hierarchy", repetitions=args.repetitions
                ),
            )
        else:
            fit(
                data,
                config,
                args.version,
                args.root,
                args.private_root,
                commit=git_commit(),
                saved_draws=args.saved_draws,
                previous=args.previous,
            )
    except (ValueError, FileExistsError) as exc:
        log.error("%s", exc)
        return 2
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    raise SystemExit(main())
