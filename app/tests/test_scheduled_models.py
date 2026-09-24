"""Prior bootstrap, private persistence and bounded population-refit failures."""

import io
import subprocess
import zipfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pytest

from isobath import nightly, scheduled
from isobath.inference import artifact
from isobath.inference.project import InferenceConfig, place
from isobath.items import read
from pipeline.autofit import extract_batch
from pipeline.bootstrap import build, design


@pytest.fixture(scope="module")
def prior():
    return build(read([Path(__file__).resolve().parents[1] / "items"]), "0.2", draws=8)


def test_prior_is_design_based_without_fake_observed_groups(prior):
    assert prior.can_place
    assert not prior.has_regions
    assert prior.stage == "PRIOR"
    assert prior.meta["n_observers"] == 0
    assert not prior.arrays["draws_occupied"].any()
    assert np.all(prior.arrays["draws_T"] == 0)
    items = read([Path(__file__).resolve().parents[1] / "items"])
    data = design(items, "0.2")
    for j in np.flatnonzero(data.anchors):
        assert np.all(prior.arrays["draws_Lambda"][:, j, data.domains[j]] > 0)
    same = build(items, "0.2", draws=8)
    assert same.version == prior.version
    np.testing.assert_array_equal(same.arrays["draws_tau"], prior.arrays["draws_tau"])


def test_prior_places_one_person_with_uncertainty(prior):
    answers = dict.fromkeys(prior.question_ids[:16], 4)
    p = place(prior, answers, config=InferenceConfig(warmup=8, draws=16, chains=2, seed=5))
    assert np.isfinite(p.map_xy).all()
    assert np.all(p.latent_se > 0)
    assert p.credible_region is not None
    assert p.memberships is None


def test_bundle_roundtrip_excludes_raw_fit_data(tmp_path, prior):
    artifact.save(prior, tmp_path / "models")
    private = tmp_path / "private" / f"chart-{prior.version}"
    (private / "chains").mkdir(parents=True)
    (private / "chains" / "raw.npy").write_bytes(b"not-a-handoff")
    packed = scheduled.pack(tmp_path, prior.version)
    with zipfile.ZipFile(io.BytesIO(packed)) as z:
        assert not any("chains" in name for name in z.namelist())
    restored = scheduled.unpack(packed, tmp_path / "restore", prior.version)
    np.testing.assert_array_equal(restored.arrays["draws_Lambda"], prior.arrays["draws_Lambda"])


def test_bundle_rejects_path_traversal(tmp_path, prior):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as z:
        z.writestr("../escaped", "private")
    with pytest.raises(ValueError, match="invalid private"):
        scheduled.unpack(buffer.getvalue(), tmp_path, prior.version)
    assert not list(tmp_path.iterdir())


def test_refit_interval_is_elapsed_days_not_cron_day_of_month():
    start = datetime(2026, 9, 24, tzinfo=UTC)
    assert not scheduled.refit_due(start, None)
    assert not scheduled.refit_due(start + timedelta(days=13), start)
    assert scheduled.refit_due(start + timedelta(days=14), start)
    assert scheduled.refit_due(start + timedelta(days=30), start)


@pytest.mark.parametrize(
    ("stage", "has_map", "has_model", "done"),
    [
        ("COLLECTING", False, False, False),
        ("UNCHARTED", False, False, False),
        ("PRIOR", True, True, True),
        ("CHARTED", True, False, True),
        ("COLLECTING", True, False, True),
        ("COLLECTING", False, True, True),
    ],
)
def test_only_unpublished_legacy_success_can_be_initialized(stage, has_map, has_model, done):
    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = {
        "stage": stage,
        "has_map": has_map,
        "has_model": has_model,
    }
    cutoff = datetime(2026, 9, 24, tzinfo=UTC)
    assert nightly.cutoff_done(conn, cutoff, initialize_unpublished=True) is done
    assert nightly.cutoff_done(conn, cutoff) is True


def test_legacy_nightly_cli_uses_scheduler(monkeypatch):
    main = MagicMock(return_value=0)
    monkeypatch.setattr(scheduled, "main", main)
    assert nightly.main(["--at", "2026-09-24T01:00+09:00"]) == 0
    main.assert_called_once_with(["--at", "2026-09-24T01:00+09:00"])


@pytest.mark.parametrize("failure", [False, True])
def test_refit_failure_retains_incumbent(monkeypatch, tmp_path, prior, failure):
    runner = MagicMock(return_value=MagicMock(returncode=2))
    if failure:
        runner.side_effect = subprocess.TimeoutExpired("refit", 600)
    monkeypatch.setattr(scheduled.subprocess, "run", runner)
    model, bundle = scheduled.attempt_refit(tmp_path, datetime(2026, 9, 24, tzinfo=UTC), prior)
    assert model is prior
    assert bundle is None
    assert runner.call_args.kwargs["timeout"] == scheduled.REFIT_TIMEOUT


def test_batch_extraction_uses_only_existing_access_and_current_consent():
    questions = read([Path(__file__).resolve().parents[1] / "items"])
    responses = [
        {
            "pseudo_id": uid,
            "session_id": "s",
            "question_id": 2001,
            "value": 4,
            "answered_at": datetime(2026, 9, 23, tzinfo=UTC),
            "item_set_version": "0.2",
        }
        for uid in ("consented", None)
    ]
    conn = MagicMock()
    conn.execute.side_effect = [
        MagicMock(),
        MagicMock(fetchall=lambda: questions),
        MagicMock(fetchall=lambda: responses),
    ]
    data = extract_batch(conn, "0.2", datetime(2026, 9, 24, tzinfo=UTC))
    assert data.user_ids == ["consented"]
    assert data.research_covariates is None
    sql = " ".join(c.args[0] for c in conn.execute.call_args_list)
    assert "analysis." not in sql
    assert "profiles" not in sql
    assert "app.batch_research_key" in sql
