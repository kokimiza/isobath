import numpy as np
import pytest

from isobath.inference import artifact


def test_roundtrip(tmp_path, model):
    artifact.save(model, tmp_path)
    (tmp_path / "CURRENT").write_text("test\n")
    loaded = artifact.load(tmp_path)
    assert loaded.stage == "CHARTED"
    assert loaded.question_ids == model.question_ids
    assert loaded.regions == model.regions
    for k, v in model.arrays.items():
        assert np.array_equal(loaded.arrays[k], v)
    assert loaded.can_place
    assert loaded.has_regions


def test_metadata_only_stage(tmp_path):
    m = artifact.Model(version="0", stage="COLLECTING", item_set_version="0.1")
    artifact.save(m, tmp_path)
    loaded = artifact.load(tmp_path, "0")
    assert not loaded.can_place
    assert not loaded.arrays


def test_repo_current_model_loads():
    from isobath.config import get_settings

    assert artifact.load(get_settings().models_dir).stage in artifact.STAGES


@pytest.mark.parametrize("version", ["../escape", "/absolute", "..", "a\\b", "a:b"])
def test_artifact_versions_cannot_escape_root(tmp_path, version):
    with pytest.raises(ValueError, match="version"):
        artifact.load(tmp_path, version)


def test_unobserved_component_cannot_be_silently_renormalized(tmp_path, model):
    model.arrays["draws_w"][:, :2] /= 0.9
    with pytest.raises(ValueError, match="weight"):
        artifact.save(model, tmp_path)


def test_missing_component_mapping_is_rejected(tmp_path, model):
    del model.arrays["draws_component_to_region"]
    with pytest.raises(ValueError, match="missing"):
        artifact.save(model, tmp_path)


def test_api_metadata_read_does_not_load_arrays(tmp_path, model):
    path = artifact.save(model, tmp_path)
    (path / "model.npz").write_bytes(b"not an npz")
    loaded = artifact.load(tmp_path, "test", metadata_only=True)
    assert loaded.arrays == {}
    assert loaded.stage == "CHARTED"


def test_existing_version_is_immutable(tmp_path, model):
    artifact.save(model, tmp_path)
    with pytest.raises(FileExistsError):
        artifact.save(model, tmp_path)
