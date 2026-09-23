"""statistics.md §§7, 8, 10: private training posteriors and immutable answer snapshots."""

import numpy as np
from test_statistics_sampler import small_data

from isobath.inference.training import training_placement
from pipeline.export import build_model
from pipeline.private import save_training
from pipeline.sampler import SamplerConfig, sample


def test_training_result_is_not_recomputed_as_cut_and_changed_answers_do_not_reuse_it(tmp_path):
    data = small_data()
    result = sample(data, SamplerConfig(warmup=4, draws=30, chains=4), tmp_path / "chains")
    model = build_model(data, result, version="private", seed=0, commit="test")
    save_training(data, result, model, tmp_path, require_precision=False)
    answers = {q: int(v) for q, v in zip(data.question_ids, data.answers[0], strict=True) if v}
    p = training_placement(tmp_path, model, "person-0", answers)
    assert p.inference_mode == "joint"
    assert np.allclose(p.latent, result.latent_mean[0])
    assert p.unmatched["unseen"] == 0
    assert training_placement(tmp_path, model, "person-0", {**answers, 1: 4}) is None
    assert training_placement(tmp_path, model, "unknown", answers) is None
