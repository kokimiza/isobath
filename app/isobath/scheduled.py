"""Daily placement and a bounded 14-day refit, with private state kept in PostgreSQL."""

import argparse
import io
import logging
import re
import subprocess
import sys
import tempfile
import zipfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

from pipeline.bootstrap import build

from .config import ITEM_SET_VERSION, get_settings
from .cycle import current_cutoff
from .inference import artifact
from .items import read
from .nightly import cutoff_done, run

log = logging.getLogger(__name__)
REFIT_INTERVAL = timedelta(days=14)
REFIT_TIMEOUT = 600  # placement still runs when population inference exceeds its budget
MAX_BUNDLE_BYTES = 256_000_000


def pack(root, version):
    files = list((root / "models" / f"chart-{version}").glob("*"))
    private = root / "private" / f"chart-{version}"
    files += list((private / "people").glob("*"))
    files += [p for p in (private / "users.json", private / "representative.npy") if p.exists()]
    if sum(p.stat().st_size for p in files) > MAX_BUNDLE_BYTES:
        raise ValueError("model handoff exceeds storage budget")
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(path, path.relative_to(root).as_posix())
    return output.getvalue()


def unpack(bundle, root, version):
    artifact.validate_version(version)
    prefix = re.escape(f"chart-{version}")
    allowed = re.compile(
        rf"(?:models/{prefix}/(?:metadata.json|model.npz)|"
        rf"private/{prefix}/(?:users.json|representative.npy|people/[a-f0-9]{{64}}\.(?:npz|json)))"
    )
    with zipfile.ZipFile(io.BytesIO(bundle)) as archive:
        entries = archive.infolist()
        if (
            len({e.filename for e in entries}) != len(entries)
            or sum(e.file_size for e in entries) > MAX_BUNDLE_BYTES
            or any(not allowed.fullmatch(e.filename) for e in entries)
        ):
            raise ValueError("invalid private model bundle")
        for entry in entries:
            path = root / entry.filename
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(archive.read(entry))
    model = artifact.load(root / "models", version)
    if (
        model.meta.get("private_results_required")
        and not (root / "private" / f"chart-{version}" / "people").is_dir()
    ):
        raise ValueError("private training handoff missing")
    return model


def refit_due(cutoff, last_attempt):
    return last_attempt is not None and cutoff - last_attempt >= REFIT_INTERVAL


def attempt_refit(root, cutoff, incumbent):
    version = f"auto-{cutoff:%Y%m%d}"
    command = [
        sys.executable,
        "-m",
        "pipeline.autofit",
        "--cutoff",
        cutoff.isoformat(),
        "--version",
        version,
        "--root",
        str(root / "models"),
        "--private-root",
        str(root / "private"),
    ]
    if incumbent.meta.get("private_results_required"):
        command += ["--previous", incumbent.version]
    try:
        result = subprocess.run(  # noqa: S603 - fixed module and validated artifact identifiers
            command,
            timeout=REFIT_TIMEOUT,
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if result.returncode:
            log.warning(
                "Refit rejected (exit %d); retaining %s", result.returncode, incumbent.version
            )
            return incumbent, None
        candidate = artifact.load(root / "models", version)
        if not candidate.meta.get("diagnostics", {}).get("accepted"):
            raise ValueError("candidate did not pass convergence diagnostics")
        bundle = pack(root, version)
        # Also validate the persisted handoff before accepting it.
        with tempfile.TemporaryDirectory() as verify:
            unpack(bundle, Path(verify), version)
        return candidate, bundle
    except (subprocess.TimeoutExpired, ValueError, OSError):
        log.warning("Refit timed out or failed validation; retaining %s", incumbent.version)
        return incumbent, None


def scheduled_run(settings, now):
    cutoff = current_cutoff(now)
    dsn = settings.nightly_database_url or settings.database_url
    with psycopg.connect(dsn, row_factory=dict_row, prepare_threshold=None) as conn:
        if cutoff_done(conn, cutoff, initialize_unpublished=True):
            return {"status": "skipped", "cutoff_at": cutoff.isoformat()}
        saved = conn.execute(
            """select chart_version, model_bundle from app.batch_runs
               where status = 'succeeded' and cutoff_at < %s and model_bundle is not null
               order by cutoff_at desc limit 1""",
            (cutoff,),
        ).fetchone()
        last_attempt = conn.execute(
            """select max(refit_attempt_at) as at from app.batch_runs
               where status = 'succeeded' and cutoff_at < %s""",
            (cutoff,),
        ).fetchone()["at"]
    with tempfile.TemporaryDirectory(prefix="isobath-model-") as work:
        root = Path(work)
        bundle = None
        if saved:
            model = unpack(bytes(saved["model_bundle"]), root, saved["chart_version"])
        else:
            questions = read([Path(__file__).resolve().parents[1] / "items"])
            model = build(questions, ITEM_SET_VERSION)
            artifact.save(model, root / "models")
            bundle = pack(root, model.version)
            last_attempt = cutoff  # first refit is 14 days after bootstrap, even with N=1
        if model.item_set_version != ITEM_SET_VERSION:
            raise ValueError("persisted model item set differs; a new bootstrap is required")
        incumbent, incumbent_bundle = model, bundle
        if refit_due(cutoff, last_attempt):
            model, candidate_bundle = attempt_refit(root, cutoff, model)
            bundle = candidate_bundle or bundle
            last_attempt = cutoff  # rejected fits are retried in 14 days, not every night
        directory = root / "private" / f"chart-{model.version}"
        try:
            return run(
                dsn,
                model,
                now,
                settings.chart_k,
                private_directory=directory if directory.exists() else None,
                model_bundle=bundle,
                refit_attempt_at=last_attempt,
                initialize_unpublished=True,
            )
        except Exception:
            if model is incumbent:
                raise
            # Candidate placement is transactional. Its failed positions were rolled back.
            log.warning(
                "Candidate placement failed; retrying daily update with %s", incumbent.version
            )
            directory = root / "private" / f"chart-{incumbent.version}"
            return run(
                dsn,
                incumbent,
                now,
                settings.chart_k,
                private_directory=directory if directory.exists() else None,
                model_bundle=incumbent_bundle,
                refit_attempt_at=last_attempt,
                initialize_unpublished=True,
            )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--at", type=datetime.fromisoformat)
    args = parser.parse_args(argv)
    log.info("%s", scheduled_run(get_settings(), args.at or datetime.now(UTC)))
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    raise SystemExit(main())
