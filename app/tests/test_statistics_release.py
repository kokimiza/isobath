"""statistics.md §§4.3, 6.3, 7: failures must not become published artifacts."""

import json

import numpy as np

from isobath.inference.regions import calibrated_region
from pipeline.run import main


def test_validation_smoke_is_explicitly_not_a_research_acceptance(tmp_path):
    output = tmp_path / "report.json"
    assert (
        main(
            [
                "validate",
                "--mode",
                "prior",
                "--repetitions",
                "2",
                "--people",
                "2",
                "--items",
                "4",
                "--dimensions",
                "2",
                "--output",
                str(output),
            ]
        )
        == 0
    )
    result = json.loads(output.read_text())
    assert result["acceptance_run"] is False
    assert result["repetitions"] == 2


def test_grid_region_is_checked_on_independent_chains():
    rng = np.random.default_rng(13)
    chains = rng.normal(size=(4, 1000, 2))
    result = calibrated_region(chains)
    assert result["validation_mass"] > 0.9
    assert result["validation_mcse"] > 0
    assert result["chain_split"] == "first_half/second_half"


def test_fit_rejects_tiny_unconverged_run_and_does_not_change_current(tmp_path):
    root = tmp_path / "models"
    root.mkdir()
    (root / "CURRENT").write_text("old\n")
    result = main(
        [
            "simulate-fit",
            "--version",
            "small",
            "--people",
            "1",
            "--items",
            "4",
            "--dimensions",
            "2",
            "--warmup",
            "2",
            "--draws",
            "4",
            "--root",
            str(root),
            "--private-root",
            str(tmp_path / "private"),
        ]
    )
    assert result == 2
    assert not (root / "chart-small").exists()
    assert (root / "CURRENT").read_text() == "old\n"
