"""statistics.md §7.1: distinguish a sampler draw from a verified batch result."""

from isobath.inference.project import InferenceConfig, infer, inference_diagnostics


def test_cut_diagnostics_report_inner_and_outer_uncertainty_separately(model):
    cfg = InferenceConfig(warmup=5, draws=32, chains=2, seed=9)
    draws = infer(model, {1: 4}, cfg)
    report = inference_diagnostics(model, draws, cfg)
    assert not report["accepted"]
    assert "outer_mcse_position" in report
    assert "inner" in report
