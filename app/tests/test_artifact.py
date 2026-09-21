import numpy as np

from isobath.inference import artifact


def test_roundtrip(tmp_path, model):
    artifact.save(model, tmp_path)
    (tmp_path / "CURRENT").write_text("test\n")
    loaded = artifact.load(tmp_path)
    assert loaded.stage == "SEED" and loaded.question_ids == model.question_ids
    assert loaded.regions == model.regions
    for k, v in model.arrays.items():
        assert np.array_equal(loaded.arrays[k], v)
    assert loaded.can_place and loaded.has_regions


def test_metadata_only_stage(tmp_path):
    m = artifact.Model(version="0", stage="UNCHARTED", item_set_version="0.1")
    artifact.save(m, tmp_path)
    loaded = artifact.load(tmp_path, "0")
    assert not loaded.can_place and not loaded.arrays


def test_repo_current_model_loads():
    from isobath.config import get_settings

    assert artifact.load(get_settings().models_dir).stage in artifact.STAGES
