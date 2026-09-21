import numpy as np

from isobath.inference.project import place, posterior


def simulate(model, f, rng):
    a = model.arrays
    z = a["Lambda"] @ f + rng.normal(0, np.sqrt(a["psi"]))
    return {q: float(a["mu"][i] + z[i]) for q, i in model.index.items()}


def test_recovers_latent_with_full_answers(model):
    rng = np.random.default_rng(1)
    truth, est = [], []
    for _ in range(300):
        f = rng.normal(size=3)
        truth.append(f)
        est.append(posterior(model, simulate(model, f, rng))[0])
    truth, est = np.array(truth), np.array(est)
    for d in range(3):
        assert np.corrcoef(truth[:, d], est[:, d])[0, 1] > 0.9


def test_fewer_answers_means_larger_se_and_lower_confidence(model):
    rng = np.random.default_rng(2)
    answers = simulate(model, rng.normal(size=3), rng)
    full = place(model, answers)
    part = place(model, dict(list(answers.items())[:10]))
    none = place(model, {})
    assert np.all(part.latent_se > full.latent_se)
    assert full.confidence > part.confidence > none.confidence == 0.0


def test_unknown_questions_are_ignored(model):
    assert np.allclose(posterior(model, {9999: 5})[0], 0)


def test_memberships(model):
    rng = np.random.default_rng(3)
    right = place(model, simulate(model, np.array([2.0, 0, 0]), rng))
    assert right.memberships[0]["lineage_id"] == "REGION-B"
    assert abs(sum(m["p"] for m in right.memberships) - 1) < 1e-3
    assert right.near_boundary is False
    # with no information the prior is symmetric -> boundary
    assert place(model, {}).near_boundary is True


def test_no_regions_before_seed(model):
    model.stage = "PROTO"
    assert place(model, {1: 3}).memberships is None
