"""3-D measurement, posterior coverage, and the boundary/position contract."""

from pathlib import Path

import numpy as np
import pytest
from conftest import synthetic_spatial_model

from isobath.inference.artifact import validate
from isobath.inference.regions import contains, credible_region
from isobath.inference.seas import at_position, probabilities, sea_field
from isobath.inference.training import training_placement
from isobath.items import read
from isobath.nightly import density_map
from pipeline.bootstrap import design
from pipeline.data import loading_mask, spatial_design
from pipeline.export import build_model
from pipeline.private import save_training
from pipeline.sampler import SamplerConfig, sample


def test_spatial_sampler_and_export_keep_three_real_factors(tmp_path):
    data = spatial_design(design(read([Path(__file__).resolve().parents[1] / "items"]), "0.2"))
    data.answers[:] = np.random.default_rng(9).integers(1, 6, data.answers.shape)
    result = sample(data, SamplerConfig(warmup=3, draws=8, chains=2, seed=12), tmp_path)
    assert result.coordinates.shape == (2, 8, 1, 3)
    assert np.all(np.std(result.coordinates, axis=(0, 1)) > 0)
    for draw in result.draws:
        assert np.all(draw["Lambda"][~loading_mask(data)] == 0)
    model = build_model(data, result, version="three", seed=12, commit="test", saved_draws=8)
    validate(model)
    assert model.meta["schema_version"] == 4
    np.testing.assert_array_equal(model.arrays["P"], np.eye(3))
    # Exercise the private joint-posterior handoff too; these short chains are not a release.
    save_training(data, result, model, tmp_path / "private", require_precision=False)
    answers = dict(zip(data.question_ids, map(int, data.answers[0]), strict=True))
    placement = training_placement(tmp_path / "private", model, data.user_ids[0], answers)
    assert placement.draws_x.shape == (16, 3)
    assert placement.credible_region["kind"] == "volume_hpd"


def test_spatial_artifact_rejects_a_flat_projection_or_free_anchor():
    model = synthetic_spatial_model()
    model.arrays["P"] = np.eye(3)[:2]
    with pytest.raises(ValueError, match="shape"):
        validate(model)
    model.arrays["P"] = np.eye(3)
    model.arrays["draws_Lambda"][:, 0, 2] = 0.1
    with pytest.raises(ValueError, match="triangular"):
        validate(model)


def test_volume_contains_three_dimensional_mass_and_rejects_far_z():
    rng = np.random.default_rng(193)
    draws = rng.normal(size=(4000, 3))
    region = credible_region(draws)
    assert region["kind"] == "volume_hpd"
    assert sum(region["cell_probability"]) == pytest.approx(1)
    assert region["mass"] >= 0.95
    assert region["integration_error"] < 0.01
    holdout = rng.normal(size=(8000, 3))
    assert 0.92 < contains(region, holdout).mean() < 0.99
    assert not contains(region, np.array([[0, 0, 100]]))[0]


def test_sea_boundary_and_mean_classification_use_the_z_coordinate():
    model = synthetic_spatial_model()
    # Two seas separated only along Z; X/Y alone cannot identify either.
    model.arrays["draws_m"][:] = [[0, 0, -2], [0, 0, 2], [0, 0, 0]]
    validate(model)
    values = probabilities(model, [[0, 0, -2], [0, 0, 2], [0, 0, 0]])
    np.testing.assert_allclose(values.sum(axis=1), 1)
    assert at_position(model, [0, 0, -2])["lineage_id"] == "REGION-A"
    assert at_position(model, [0, 0, 2])["lineage_id"] == "REGION-B"
    assert at_position(model, [0, 0, 0])["lineage_id"] is None
    field = sea_field(model, bins=7)
    # Grid nodes at (0,0,-2) and (0,0,+2), same flattening as the renderer.
    for i, index in enumerate([3 * 49 + 3 * 7 + 1, 3 * 49 + 3 * 7 + 5]):
        assert field["regions"][i]["values"][index] == pytest.approx(values[i, i], abs=1e-6)


def test_3d_aggregate_suppresses_people_separately_in_depth():
    points = np.array([[0.1, 0.1, 0.1]] * 3 + [[0.1, 0.1, 2]])
    chart = density_map(points, k=2)
    assert chart["space"] == "latent3-v1"
    assert sum(chart["volume"]["counts"]) == 3
    assert not any(density_map(np.empty((0, 3)), k=2)["volume"]["counts"])
